/**
 * 学生会官网 - 前后端联动脚本
 * 所有 AJAX 请求通过此文件与 Flask 后端通信，避免跨域问题。
 * 使用方式：必须通过 Flask 启动后访问 http://127.0.0.1:5000/ 打开页面。
 */

(function () {
  'use strict';

  // 后端地址：通过 Flask 打开页面时用相对路径即可（同源）；若本地直接打开 HTML 则改为 'http://127.0.0.1:5000'
  window.API_BASE = (function () {
    if (typeof location !== 'undefined' && location.protocol === 'file:') {
      return 'http://127.0.0.1:5000';
    }
    return '';
  })();

  /**
   * 获取最新通知列表
   * @returns {Promise} axios 请求，resolve 为 { data: Array }
   */
  window.getNotices = function () {
    return window.axios.get(API_BASE + '/api/get_notices');
  };

  /**
   * 获取活动列表
   * @returns {Promise} axios 请求，resolve 为 { data: Array }
   */
  window.getActivities = function () {
    return window.axios.get(API_BASE + '/api/get_activities');
  };

  /**
   * 获取成员列表
   * @returns {Promise} axios 请求，resolve 为 { data: Array }
   */
  window.getMembers = function () {
    return window.axios.get(API_BASE + '/api/get_members');
  };

  /**
   * 提交意见反馈到后端，并存入数据库
   * @param {Object} data - { name: string, email: string, content: string }
   * @returns {Promise} axios 请求，resolve 为 { data: { success: boolean, message?: string } }
   */
  window.submitFeedback = function (data) {
    return window.axios.post(API_BASE + '/api/submit_feedback', data, {
      headers: { 'Content-Type': 'application/json' }
    });
  };
})();
