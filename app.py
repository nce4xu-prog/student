# -*- coding: utf-8 -*-
"""
学生会官网 Flask 后端
与 index / activities / members / feedback 四个前端页面同目录运行。
启动后访问 http://127.0.0.1:5000/ 即可；前端会自动从接口加载数据。
"""

import os
import sqlite3
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session, g

# =============================================================================
# 【修改提示 1】数据库路径
# 使用 feedback.db，与 app.py 同目录。反馈数据会永久存入该数据库的 feedback 表。
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'feedback.db')

# =============================================================================
# 【修改提示 2】邮箱配置（提交反馈后发邮件到接收邮箱）
# 请替换为自己的：接收邮箱、发送邮箱、SMTP 地址、端口、授权码。
# QQ 邮箱：smtp.qq.com，端口 465，在 QQ 邮箱设置里开启 SMTP 并获取授权码。
# 163 邮箱：smtp.163.com，端口 465，同样需授权码。
# 若暂时不发邮件，可将 SEND_MAIL_ON_FEEDBACK 设为 False。
# =============================================================================
MAIL_RECEIVER = 'your_receiver@example.com'   # 接收反馈的邮箱（必改）
MAIL_SMTP = 'smtp.qq.com'                     # SMTP 服务器
MAIL_PORT = 465
MAIL_SENDER = 'your_sender@qq.com'            # 发送者邮箱（必改）
MAIL_AUTH = 'your_smtp_auth_code'             # SMTP 授权码，非登录密码（必改）
SEND_MAIL_ON_FEEDBACK = True                  # 是否在提交反馈时发邮件；关闭可设为 False

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
app.config['SECRET_KEY'] = 'xx-student-union-secret-key-please-change-in-production'
app.config['JSON_AS_ASCII'] = False


# -----------------------------------------------------------------------------
# 跨域 CORS：允许前端页面调用后端接口（解决跨域问题）
# -----------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# -----------------------------------------------------------------------------
# 数据库
# -----------------------------------------------------------------------------

def get_db():
    """获取当前请求的数据库连接，放到 g 里复用。"""
    if not hasattr(g, '_db'):
        g._db = sqlite3.connect(DATABASE)
        g._db.row_factory = sqlite3.Row
    return g._db


@app.teardown_appcontext
def close_db(evt=None):
    if hasattr(g, '_db'):
        g._db.close()


def init_db():
    """创建 5 张表并插入示例数据。若表已存在则跳过建表，仅确保有管理员。"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # 通知表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            publish_time TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # 活动表：status 为 upcoming / ongoing / finished
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT NOT NULL,
            image_url TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # 成员表：department 如 主席团、学习部、文体部
    cur.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            role TEXT NOT NULL,
            intro TEXT NOT NULL,
            image_url TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # 反馈表
    cur.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # 管理员表（账号 admin，密码 123456，使用 werkzeug 加密）
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # 检查是否已有管理员，没有则插入
    cur.execute('SELECT 1 FROM admin WHERE username = ?', ('admin',))
    if cur.fetchone() is None:
        from werkzeug.security import generate_password_hash
        pw = generate_password_hash('123456', method='pbkdf2:sha256')
        cur.execute(
            'INSERT INTO admin (username, password_hash, created_at) VALUES (?, ?, ?)',
            ('admin', pw, now)
        )

    # 示例数据：仅当表为空时插入
    cur.execute('SELECT COUNT(*) FROM notices')
    if cur.fetchone()[0] == 0:
        notices = [
            ('关于举办 2026 年春季校园科技节的通知', '为激发同学们的创新意识和实践能力，学生会将于 3 月下旬举办校园科技节，欢迎各班积极报名参加。', '2026-03-01'),
            ('校园艺术节节目征集通知', '欢迎热爱音乐、舞蹈、朗诵、戏剧等艺术形式的同学报名参加，展示才艺、丰富校园文化生活。', '2026-02-20'),
            ('学生会纳新面试安排通知', '已报名加入学生会的同学，请按照年级和时间段参加面试，具体安排见教务处公告栏和微信群通知。', '2026-02-15'),
            ('关于开展校园文明督导活动的通知', '为营造整洁有序的校园环境，学生会将组织文明督导小组，对校园卫生、礼貌用语等进行引导和检查。', '2026-02-05'),
            ('冬季安全教育主题班会通知', '请各班班主任结合学校统一资料，组织开展冬季安全教育主题班会，重点提醒交通、用电和网络安全。', '2026-01-28'),
        ]
        for t, c, pt in notices:
            cur.execute(
                'INSERT INTO notices (title, content, publish_time, created_at) VALUES (?, ?, ?, ?)',
                (t, c, pt, now)
            )

    cur.execute('SELECT COUNT(*) FROM activities')
    if cur.fetchone()[0] == 0:
        activities = [
            ('2026 年春季校园科技节', '2026-03-25 14:00 - 17:30', '由学生会学习部组织，包含科技作品展示、科普讲座和现场互动实验等环节，欢迎对科技感兴趣的同学报名参加。', 'upcoming', 'https://images.pexels.com/photos/3184296/pexels-photo-3184296.jpeg?auto=compress&cs=tinysrgb&w=1200'),
            ('校园读书节 —— 好书分享会', '2026-04-10 15:30 - 17:00', '邀请同学们推荐自己喜欢的一本书，可以进行读书分享、朗读片段或展示相关手抄报作品，营造良好的阅读氛围。', 'upcoming', 'https://images.pexels.com/photos/3059748/pexels-photo-3059748.jpeg?auto=compress&cs=tinysrgb&w=1200'),
            ('校园环保主题海报征集', '2026-02-20 - 2026-03-05', '由学生会宣传部发起，征集以「低碳生活」「绿色校园」为主题的原创海报作品，优秀作品将在校园公告栏和公众号展示。', 'ongoing', 'https://images.pexels.com/photos/256541/pexels-photo-256541.jpeg?auto=compress&cs=tinysrgb&w=1200'),
            ('校园篮球班级联赛', '2026-02-18 - 2026-03-10（放学后）', '由文体部组织，各班组队参加，分年级进行小组赛和决赛，倡导健康运动与团队合作精神。', 'ongoing', 'https://images.pexels.com/photos/267885/pexels-photo-267885.jpeg?auto=compress&cs=tinysrgb&w=1200'),
            ('迎新文艺晚会', '2026-01-15 18:30 - 20:30', '由学生会主办，各社团联合参与，节目形式包括合唱、舞蹈、朗诵、小品等，为新同学展示校园风采。', 'finished', 'https://images.pexels.com/photos/2280551/pexels-photo-2280551.jpeg?auto=compress&cs=tinysrgb&w=1200'),
            ('期末复习互助交流会', '2025-12-20 16:00 - 17:30', '学习部组织优秀同学分享复习方法和资料，同学之间自由提问与交流，帮助大家更好地准备期末考试。', 'finished', 'https://images.pexels.com/photos/3184611/pexels-photo-3184611.jpeg?auto=compress&cs=tinysrgb&w=1200'),
        ]
        for title, time_range, desc, status, img in activities:
            cur.execute(
                'INSERT INTO activities (title, start_time, end_time, description, status, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (title, time_range, time_range, desc, status, img, now)
            )

    cur.execute('SELECT COUNT(*) FROM members')
    if cur.fetchone()[0] == 0:
        members = [
            ('张晨曦', '主席团', '学生会主席', '负责学生会整体工作统筹，协调各部门沟通与合作，代表学生向学校反馈意见和建议。', ''),
            ('李雨桐', '主席团', '副主席', '协助主席开展日常工作，重点负责活动策划与流程把控，保证活动顺利、安全、有序进行。', ''),
            ('王子涵', '主席团', '副主席', '负责对接各年级学生会成员，收集同学们的需求和建议，并参与制定学生会工作计划。', ''),
            ('刘思涵', '学习部', '部长', '负责策划学习经验交流会、学习互助活动等，组织收集和分享优秀学习方法与资料。', ''),
            ('陈子豪', '学习部', '干事', '协助整理学习资料、制作复习指南，并参与组织考试经验分享与错题交流活动。', ''),
            ('赵一鸣', '学习部', '干事', '负责联系各班学习委员，收集同学在学习方面的困难和建议，并反馈给老师与学生会。', ''),
            ('周子悦', '文体部', '部长', '负责策划校园艺术节、迎新晚会等文艺活动，以及组织各类文体比赛与节目排练。', ''),
            ('高宇航', '文体部', '干事', '主要负责篮球联赛、运动会等体育活动的场地协调、秩序维护与物资准备。', ''),
            ('孙语彤', '文体部', '干事', '负责联系节目表演同学，协助音响、灯光等舞台事务，保证演出效果和现场氛围。', ''),
        ]
        for name, dept, role, intro, img in members:
            cur.execute(
                'INSERT INTO members (name, department, role, intro, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (name, dept, role, intro, (img or None), now)
            )

    db.commit()
    db.close()


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


# -----------------------------------------------------------------------------
# 邮件发送（反馈提交后）
# -----------------------------------------------------------------------------

def send_feedback_mail(name, email, content):
    """将反馈内容以邮件形式发送到 MAIL_RECEIVER。失败不抛异常，只记日志。"""
    if not SEND_MAIL_ON_FEEDBACK:
        return
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f'[学生会官网] 来自 {name} 的意见反馈'
        msg['From'] = MAIL_SENDER
        msg['To'] = MAIL_RECEIVER
        body = f'''姓名：{name}\n邮箱：{email}\n\n反馈内容：\n{content}\n'''
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP_SSL(MAIL_SMTP, MAIL_PORT) as s:
            s.login(MAIL_SENDER, MAIL_AUTH)
            s.sendmail(MAIL_SENDER, MAIL_RECEIVER, msg.as_string())
    except Exception as e:
        print('[邮件发送失败]', str(e))


# -----------------------------------------------------------------------------
# 前端页面路由（与 4 个 HTML 同目录，直接提供静态文件）
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/index.html')
def index_html():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/activities.html')
def activities():
    return send_from_directory(BASE_DIR, 'activities.html')


@app.route('/members.html')
def members():
    return send_from_directory(BASE_DIR, 'members.html')


@app.route('/feedback.html')
def feedback():
    return send_from_directory(BASE_DIR, 'feedback.html')


@app.route('/admin.html')
def admin_page():
    return send_from_directory(BASE_DIR, 'admin.html')


@app.route('/admin')
def admin_redirect():
    """访问 /admin 时直接打开后台管理页。"""
    return send_from_directory(BASE_DIR, 'admin.html')


@app.route('/script.js')
def script_js():
    """前端统一调用的 script.js，与后端联动。"""
    return send_from_directory(BASE_DIR, 'script.js')


# 静态资源：JS/CSS 等若在子目录，可单独配置；当前前端均 CDN，可不处理。
# 若后续有本地静态文件，可加 static 路由。


# -----------------------------------------------------------------------------
# 公开 API
# -----------------------------------------------------------------------------

@app.route('/api/get_notices', methods=['GET'])
def get_notices():
    """获取通知列表，按发布时间倒序。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, title, content, publish_time FROM notices ORDER BY publish_time DESC')
    rows = cur.fetchall()
    return jsonify([_row_to_dict(r) for r in rows])


@app.route('/api/get_activities', methods=['GET'])
def get_activities():
    """获取活动列表。前端可按 status 筛选。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, title, description, start_time, end_time, status, image_url FROM activities ORDER BY id')
    rows = cur.fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        d['start_time'] = d.get('start_time') or ''
        d['end_time'] = d.get('end_time') or ''
        out.append(d)
    return jsonify(out)


@app.route('/api/get_members', methods=['GET'])
def get_members():
    """获取成员列表。前端按 department 分组展示。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, name, department, role, intro, image_url FROM members ORDER BY department, id')
    rows = cur.fetchall()
    return jsonify([_row_to_dict(r) for r in rows])


def _email_valid(e):
    if not e or not isinstance(e, str):
        return False
    e = e.strip()
    if not e:
        return False
    return bool(re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', e))


@app.route('/api/submit_feedback', methods=['OPTIONS'])
def submit_feedback_options():
    """CORS 预检请求，直接返回 204。"""
    return '', 204


@app.route('/api/submit_feedback', methods=['POST'])
def submit_feedback():
    """
    提交意见反馈。
    请求体 JSON：{ "name": "...", "email": "...", "content": "..." }
    会写入 feedback 表，并尝试发送邮件到 MAIL_RECEIVER。
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    content = (data.get('content') or '').strip()

    if not name or not content:
        return jsonify({'success': False, 'message': '请填写完整信息'}), 400
    if not _email_valid(email):
        return jsonify({'success': False, 'message': '请输入正确的邮箱格式'}), 400

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'INSERT INTO feedback (name, email, content, created_at) VALUES (?, ?, ?, ?)',
        (name, email, content, now)
    )
    db.commit()

    send_feedback_mail(name, email, content)
    return jsonify({'success': True})


# -----------------------------------------------------------------------------
# 后台登录与鉴权
# -----------------------------------------------------------------------------

def admin_required(f):
    """要求已登录管理员，否则返回 401。"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return wrapped


@app.route('/api/admin_login', methods=['POST'])
def admin_login():
    """
    管理员登录。账号 admin，密码 123456。
    请求体 JSON：{ "username": "...", "password": "..." }
    成功后在 session 中标记已登录。
    """
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'success': False, 'message': '请填写用户名和密码'}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, password_hash FROM admin WHERE username = ?', (username,))
    row = cur.fetchone()
    if not row:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

    from werkzeug.security import check_password_hash
    if not check_password_hash(row['password_hash'], password):
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

    session['admin_logged_in'] = True
    session['admin_username'] = username
    return jsonify({'success': True})


@app.route('/api/admin_logout', methods=['POST'])
def admin_logout():
    """退出登录。"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return jsonify({'success': True})


@app.route('/api/admin/check', methods=['GET'])
def admin_check():
    """检查是否已登录。"""
    return jsonify({'logged_in': bool(session.get('admin_logged_in'))})


# -----------------------------------------------------------------------------
# 后台 CRUD：通知、活动、成员
# -----------------------------------------------------------------------------

@app.route('/api/admin/notices', methods=['GET'])
@admin_required
def admin_list_notices():
    """获取通知列表（管理用）。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, title, content, publish_time, created_at FROM notices ORDER BY publish_time DESC')
    return jsonify([_row_to_dict(r) for r in cur.fetchall()])


@app.route('/api/admin/notices', methods=['POST'])
@admin_required
def admin_create_notice():
    """新增通知。JSON: title, content, publish_time。"""
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    publish_time = (data.get('publish_time') or '').strip()
    if not title or not content or not publish_time:
        return jsonify({'success': False, 'message': '缺少 title / content / publish_time'}), 400
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'INSERT INTO notices (title, content, publish_time, created_at) VALUES (?, ?, ?, ?)',
        (title, content, publish_time, now)
    )
    db.commit()
    return jsonify({'success': True, 'id': cur.lastrowid})


@app.route('/api/admin/notices/<int:nid>', methods=['PUT'])
@admin_required
def admin_update_notice(nid):
    """更新通知。JSON: title, content, publish_time（均可选）。"""
    data = request.get_json() or {}
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id FROM notices WHERE id = ?', (nid,))
    if not cur.fetchone():
        return jsonify({'success': False, 'message': '通知不存在'}), 404
    updates = []
    params = []
    for k in ('title', 'content', 'publish_time'):
        v = data.get(k)
        if v is not None:
            updates.append(f'{k} = ?')
            params.append(v.strip() if isinstance(v, str) else v)
    if not updates:
        return jsonify({'success': True})
    params.append(nid)
    cur.execute('UPDATE notices SET ' + ', '.join(updates) + ' WHERE id = ?', params)
    db.commit()
    return jsonify({'success': True})


@app.route('/api/admin/notices/<int:nid>', methods=['DELETE'])
@admin_required
def admin_delete_notice(nid):
    """删除通知。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM notices WHERE id = ?', (nid,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'success': False, 'message': '通知不存在'}), 404
    return jsonify({'success': True})


@app.route('/api/admin/activities', methods=['GET'])
@admin_required
def admin_list_activities():
    """获取活动列表（管理用）。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, title, description, start_time, end_time, status, image_url, created_at FROM activities ORDER BY id')
    return jsonify([_row_to_dict(r) for r in cur.fetchall()])


@app.route('/api/admin/activities', methods=['POST'])
@admin_required
def admin_create_activity():
    """新增活动。JSON: title, description, start_time, end_time, status, image_url。"""
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    desc = (data.get('description') or '').strip()
    st = (data.get('start_time') or '').strip()
    et = (data.get('end_time') or '').strip()
    status = (data.get('status') or 'upcoming').strip() or 'upcoming'
    img = (data.get('image_url') or '').strip()
    if not title or not desc:
        return jsonify({'success': False, 'message': '缺少 title / description'}), 400
    if status not in ('upcoming', 'ongoing', 'finished'):
        status = 'upcoming'
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'INSERT INTO activities (title, description, start_time, end_time, status, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (title, desc, st, et, status, img or None, now)
    )
    db.commit()
    return jsonify({'success': True, 'id': cur.lastrowid})


@app.route('/api/admin/activities/<int:aid>', methods=['PUT'])
@admin_required
def admin_update_activity(aid):
    """更新活动。"""
    data = request.get_json() or {}
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id FROM activities WHERE id = ?', (aid,))
    if not cur.fetchone():
        return jsonify({'success': False, 'message': '活动不存在'}), 404
    updates = []
    params = []
    for k in ('title', 'description', 'start_time', 'end_time', 'status', 'image_url'):
        v = data.get(k)
        if v is not None:
            updates.append(f'{k} = ?')
            params.append(v.strip() if isinstance(v, str) else v)
    if not updates:
        return jsonify({'success': True})
    params.append(aid)
    cur.execute('UPDATE activities SET ' + ', '.join(updates) + ' WHERE id = ?', params)
    db.commit()
    return jsonify({'success': True})


@app.route('/api/admin/activities/<int:aid>', methods=['DELETE'])
@admin_required
def admin_delete_activity(aid):
    """删除活动。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM activities WHERE id = ?', (aid,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'success': False, 'message': '活动不存在'}), 404
    return jsonify({'success': True})


@app.route('/api/admin/members', methods=['GET'])
@admin_required
def admin_list_members():
    """获取成员列表（管理用）。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, name, department, role, intro, image_url, created_at FROM members ORDER BY department, id')
    return jsonify([_row_to_dict(r) for r in cur.fetchall()])


@app.route('/api/admin/members', methods=['POST'])
@admin_required
def admin_create_member():
    """新增成员。JSON: name, department, role, intro, image_url。"""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    dept = (data.get('department') or '').strip()
    role = (data.get('role') or '').strip()
    intro = (data.get('intro') or '').strip()
    img = (data.get('image_url') or '').strip()
    if not name or not dept or not role or not intro:
        return jsonify({'success': False, 'message': '缺少 name / department / role / intro'}), 400
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'INSERT INTO members (name, department, role, intro, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (name, dept, role, intro, img or None, now)
    )
    db.commit()
    return jsonify({'success': True, 'id': cur.lastrowid})


@app.route('/api/admin/members/<int:mid>', methods=['PUT'])
@admin_required
def admin_update_member(mid):
    """更新成员。"""
    data = request.get_json() or {}
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id FROM members WHERE id = ?', (mid,))
    if not cur.fetchone():
        return jsonify({'success': False, 'message': '成员不存在'}), 404
    updates = []
    params = []
    for k in ('name', 'department', 'role', 'intro', 'image_url'):
        v = data.get(k)
        if v is not None:
            updates.append(f'{k} = ?')
            params.append(v.strip() if isinstance(v, str) else v)
    if not updates:
        return jsonify({'success': True})
    params.append(mid)
    cur.execute('UPDATE members SET ' + ', '.join(updates) + ' WHERE id = ?', params)
    db.commit()
    return jsonify({'success': True})


@app.route('/api/admin/members/<int:mid>', methods=['DELETE'])
@admin_required
def admin_delete_member(mid):
    """删除成员。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM members WHERE id = ?', (mid,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'success': False, 'message': '成员不存在'}), 404
    return jsonify({'success': True})


@app.route('/api/admin/feedback', methods=['GET'])
@admin_required
def admin_list_feedback():
    """获取反馈列表（仅查看，无增删改）。"""
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, name, email, content, created_at FROM feedback ORDER BY created_at DESC')
    return jsonify([_row_to_dict(r) for r in cur.fetchall()])


# -----------------------------------------------------------------------------
# 启动
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    print('数据库已初始化：', DATABASE)
    print('前端访问：http://127.0.0.1:5000/')
    print('后台管理：http://127.0.0.1:5000/admin.html （账号 admin，密码 123456）')
    app.run(host='127.0.0.1', port=5000, debug=True)
