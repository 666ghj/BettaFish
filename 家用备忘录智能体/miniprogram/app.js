// app.js
App({
  globalData: {
    token: '',
    memberId: '',
    hasFamily: false,
    role: '',
    familyInfo: null,
  },

  onLaunch() {
    // 检查登录状态
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
      this.globalData.memberId = wx.getStorageSync('memberId');
      this.globalData.hasFamily = wx.getStorageSync('hasFamily') === 'true';
      this.globalData.role = wx.getStorageSync('role');
    }
  },

  setLoginInfo(data) {
    this.globalData.token = data.token;
    this.globalData.memberId = data.member_id;
    this.globalData.hasFamily = data.has_family;
    this.globalData.role = data.role || '';
    wx.setStorageSync('token', data.token);
    wx.setStorageSync('memberId', data.member_id);
    wx.setStorageSync('hasFamily', String(data.has_family));
    wx.setStorageSync('role', data.role || '');
  },

  logout() {
    this.globalData.token = '';
    this.globalData.memberId = '';
    this.globalData.hasFamily = false;
    this.globalData.role = '';
    wx.removeStorageSync('token');
    wx.removeStorageSync('memberId');
    wx.removeStorageSync('hasFamily');
    wx.removeStorageSync('role');
  },
});