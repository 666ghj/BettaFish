// 微信小程序 API 封装
const BASE_URL = 'http://localhost:8000/api'; // 开发环境，生产环境替换为正式域名

const request = (method, path, data = {}) => {
  const app = getApp();
  const token = app.globalData.token;

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${path}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      success(res) {
        if (res.statusCode === 200 || res.statusCode === 201) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          // token 过期，跳转登录
          wx.navigateTo({ url: '/pages/profile/profile' });
          reject(new Error('登录已过期'));
        } else {
          reject(new Error(res.data.detail || '请求失败'));
        }
      },
      fail(err) {
        reject(new Error('网络错误'));
      },
    });
  });
};

module.exports = {
  // ===== 认证 =====
  login(code) {
    return request('POST', '/auth/login', { code });
  },

  getMe() {
    return request('GET', '/auth/me');
  },

  // ===== 家庭空间 =====
  createFamily(name, role) {
    return request('POST', '/family/create', { name, role });
  },

  joinFamily(inviteCode, role) {
    return request('POST', '/family/join', { invite_code: inviteCode, role });
  },

  getFamilyInfo() {
    return request('GET', '/family/info');
  },

  refreshInviteCode() {
    return request('POST', '/family/refresh-code');
  },

  // ===== 对话 =====
  sendMessage(message) {
    return request('POST', '/chat', { message });
  },

  // ===== 缴费 =====
  getPaymentItems() {
    return request('GET', '/payment/items');
  },

  updatePaymentItem(id, data) {
    return request('PUT', `/payment/items/${id}`, data);
  },

  getPaymentRecords() {
    return request('GET', '/payment/records');
  },

  createPaymentRecord(data) {
    return request('POST', '/payment/records', data);
  },

  // ===== 购物清单 =====
  getShoppingItems(listType, status) {
    let path = '/shopping/items';
    const params = {};
    if (listType) params.list_type = listType;
    if (status) params.status = status;
    const query = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
    if (query) path += `?${query}`;
    return request('GET', path);
  },

  createShoppingItem(data) {
    return request('POST', '/shopping/items', data);
  },

  updateShoppingItem(id, data) {
    return request('PUT', `/shopping/items/${id}`, data);
  },

  deleteShoppingItem(id) {
    return request('DELETE', `/shopping/items/${id}`);
  },

  agreeShoppingItem(id, agreement) {
    return request('POST', `/shopping/items/${id}/agree`, { agreement });
  },

  commentShoppingItem(id, content) {
    return request('POST', `/shopping/items/${id}/comment`, { content });
  },

  purchaseShoppingItem(id, data) {
    return request('POST', `/shopping/items/${id}/purchase`, data);
  },

  // ===== 收支记录 =====
  getFinanceRecords(year, month, category) {
    let path = '/finance/records';
    const params = {};
    if (year) params.year = year;
    if (month) params.month = month;
    if (category) params.category = category;
    const query = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
    if (query) path += `?${query}`;
    return request('GET', path);
  },

  getFinanceStats(year, month) {
    let path = '/finance/stats';
    const params = {};
    if (year) params.year = year;
    if (month) params.month = month;
    const query = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
    if (query) path += `?${query}`;
    return request('GET', path);
  },

  createFinanceRecord(data) {
    return request('POST', '/finance/records', data);
  },

  // ===== 车辆管理 =====
  getVehicleInfo() {
    return request('GET', '/vehicle/info');
  },

  updateVehicleInfo(data) {
    return request('PUT', '/vehicle/info', data);
  },

  getVehicleExpenses() {
    return request('GET', '/vehicle/expenses');
  },

  createVehicleExpense(data) {
    return request('POST', '/vehicle/expenses', data);
  },

  getDrivingLicense() {
    return request('GET', '/vehicle/license');
  },

  addViolation(data) {
    return request('POST', '/vehicle/license', data);
  },

  // ===== 纪念日 =====
  getAnniversaries() {
    return request('GET', '/anniversary/list');
  },

  createAnniversary(data) {
    return request('POST', '/anniversary', data);
  },

  updateAnniversary(id, data) {
    return request('PUT', `/anniversary/${id}`, data);
  },

  deleteAnniversary(id) {
    return request('DELETE', `/anniversary/${id}`);
  },

  getAnniversaryPlans(id) {
    return request('GET', `/anniversary/${id}/plans`);
  },

  createAnniversaryPlan(id, data) {
    return request('POST', `/anniversary/${id}/plans`, data);
  },

  getWishList() {
    return request('GET', '/anniversary/wish-list');
  },

  addWishItem(data) {
    return request('POST', '/anniversary/wish-list', data);
  },
};