# XX中学学生会官网

前端：`index.html` / `activities.html` / `members.html` / `feedback.html`  
后端：`app.py`（Flask + SQLite）

## 本地运行

1. **安装依赖**（终端在项目目录执行）：
   ```bash
   pip install -r requirements.txt
   ```

2. **启动后端**：
   ```bash
   python app.py
   ```

3. **浏览器访问**：
   - 官网首页：<http://127.0.0.1:5000/>
   - 活动通知：<http://127.0.0.1:5000/activities.html>
   - 成员页：<http://127.0.0.1:5000/members.html>
   - 意见反馈：<http://127.0.0.1:5000/feedback.html>
   - 后台管理：<http://127.0.0.1:5000/admin.html> 或 <http://127.0.0.1:5000/admin>

**注意**：必须通过上述地址访问（不能直接双击打开 HTML 文件），否则前端无法从接口加载数据。

## 后台管理

- 账号：`admin`  
- 密码：`123456`  
- 登录后可编辑通知、活动、成员，以及查看反馈列表。

## 修改配置

- **数据库路径**：在 `app.py` 顶部修改 `DATABASE`。
- **邮箱配置**（反馈提交后发邮件）：在 `app.py` 顶部修改 `MAIL_RECEIVER`、`MAIL_SENDER`、`MAIL_AUTH` 等；若暂不发邮件，将 `SEND_MAIL_ON_FEEDBACK` 设为 `False`。

## 数据库

- 首次运行会自动创建 `student_union.db`，并插入示例数据。
- 表：`notices`、`activities`、`members`、`feedback`、`admin`。

- 启动终端，打开数据库  sqlite3 feedback.db
- 在 sqlite> 里输入：SELECT * FROM feedback;可查看表数据。
- 在 sqlite> 里输入 .quit 回车退出数据库
