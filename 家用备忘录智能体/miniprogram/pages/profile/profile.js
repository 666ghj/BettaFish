// pages/profile/profile.js
const api = require('../../utils/api');

Page({
  data: {
    loggedIn: false,
    member: null,
    family: null,
    inviteCode: '',
    showCreateFamily: false,
    showJoinFamily: false,
    familyName: '我的家庭',
    joinCode: '',
    role: 'husband',
    joinRole: 'wife',
  },

  onShow() {
    this.checkLogin();
  },

  checkLogin() {
    const app = getApp();
    const token = app.globalData.token;
    if (token) {
      this.setData({ loggedIn: true });
      this.loadData();
    } else {
      this.setData({ loggedIn: false });
    }
  },

  async loadData() {
    try {
      const me = await api.getMe();
      const family = await api.getFamilyInfo();
      this.setData({
        member: me,
        family: family,
        inviteCode: family.invite_code || '',
      });
    } catch (e) {
      console.error('加载数据失败', e);
    }
  },

  // 微信登录
  wxLogin() {
    wx.login({
      success: async (res) => {
        if (res.code) {
          try {
            const data = await api.login(res.code);
            const app = getApp();
            app.setLoginInfo(data);
            this.setData({ loggedIn: true });
            this.loadData();

            if (!data.has_family) {
              wx.showModal({
                title: '加入家庭',
                content: '你还没有家庭空间，创建或加入一个？',
                confirmText: '创建家庭',
                cancelText: '加入家庭',
                success: (res) => {
                  if (res.confirm) {
                    this.setData({ showCreateFamily: true });
                  } else {
                    this.setData({ showJoinFamily: true });
                  }
                },
              });
            }
          } catch (e) {
            wx.showToast({ title: '登录失败', icon: 'none' });
          }
        }
      },
    });
  },

  // 创建家庭
  async onCreateFamily() {
    try {
      const data = await api.createFamily(this.data.familyName, this.data.role);
      const app = getApp();
      app.globalData.hasFamily = true;
      app.globalData.role = this.data.role;
      this.setData({
        showCreateFamily: false,
        family: data,
        inviteCode: data.invite_code,
      });
      wx.showToast({ title: '创建成功', icon: 'success' });
      // 复制邀请码
      wx.setClipboardData({ data: data.invite_code });
    } catch (e) {
      wx.showToast({ title: '创建失败', icon: 'none' });
    }
  },

  // 加入家庭
  async onJoinFamily() {
    try {
      const data = await api.joinFamily(this.data.joinCode, this.data.joinRole);
      const app = getApp();
      app.globalData.hasFamily = true;
      app.globalData.role = this.data.joinRole;
      this.setData({ showJoinFamily: false });
      wx.showToast({ title: '加入成功', icon: 'success' });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '邀请码无效或已过期', icon: 'none' });
    }
  },

  // 刷新邀请码
  async onRefreshCode() {
    try {
      const data = await api.refreshInviteCode();
      this.setData({ inviteCode: data.invite_code });
      wx.setClipboardData({ data: data.invite_code });
      wx.showToast({ title: '已复制新邀请码', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: '刷新失败', icon: 'none' });
    }
  },

  logout() {
    wx.showModal({
      title: '退出登录',
      content: '确定退出登录？',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          app.logout();
          this.setData({ loggedIn: false, member: null, family: null });
        }
      },
    });
  },
});