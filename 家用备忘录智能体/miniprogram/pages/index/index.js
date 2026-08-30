// pages/index/index.js
const api = require('../../utils/api');

Page({
  data: {
    hasFamily: false,
    role: '',
    roleLabel: '',
    searchValue: '',
    memoCount: 0,
    todayMemos: [],
    upcomingMemos: [],
    overdueMemos: [],
    monthlyExpense: 0,
    monthlyIncome: 0,
    activities: [],
    quickEntries: [
      { icon: '💬', name: '对话', url: '/pages/chat/chat' },
      { icon: '🛒', name: '购物', url: '/pages/shopping/shopping' },
      { icon: '💰', name: '缴费', url: '/pages/payment/payment' },
      { icon: '🚗', name: '车辆', url: '/pages/vehicle/vehicle' },
      { icon: '🎉', name: '纪念日', url: '/pages/anniversary/anniversary' },
      { icon: '📊', name: '收支', url: '/pages/finance/finance' },
    ],
  },

  onShow() {
    const app = getApp();
    if (app.globalData.token) {
      const role = app.globalData.role || '';
      const roleLabel = role === 'husband' ? '老公' : role === 'wife' ? '老婆' : '';
      this.setData({
        hasFamily: app.globalData.hasFamily,
        role,
        roleLabel,
      });
      if (app.globalData.hasFamily) {
        this.loadData();
      }
    }
  },

  onSearchInput(e) {
    this.setData({ searchValue: e.detail.value });
  },

  onSearch() {
    const keyword = this.data.searchValue.trim();
    if (keyword) {
      wx.navigateTo({ url: '/pages/chat/chat' });
    }
  },

  async loadData() {
    try {
      // 加载待办
      const memos = await api.sendMessage('查一下我的待办');
      if (memos && memos.data) {
        const now = Date.now();
        const overdue = [];
        const today = [];
        const upcoming = [];
        memos.data.forEach(m => {
          if (m.status === 'pending') {
            const dueTime = new Date(m.due_time).getTime();
            if (dueTime < now) overdue.push(m);
            else if (dueTime < now + 86400000) today.push(m);
            else upcoming.push(m);
          }
        });
        this.setData({
          memoCount: memos.data.length,
          overdueMemos: overdue,
          todayMemos: today,
          upcomingMemos: upcoming,
        });
      }

      // 加载月度收支
      const stats = await api.getFinanceStats();
      if (stats) {
        this.setData({
          monthlyExpense: stats.total_expense,
          monthlyIncome: stats.total_income,
        });
      }

      // 模拟动态流数据（后续从后端获取）
      this.setData({
        activities: [
          { type: 'alert', text: '💡 车险将于9月15日到期', time: '系统提醒' },
          { type: 'action', text: '📝 你有1条待办逾期', time: '刚刚' },
          { type: 'action', text: '🛒 购物清单有3件待商榷', time: '系统提醒' },
        ],
      });
    } catch (e) {
      console.error('加载首页数据失败', e);
    }
  },

  navigateTo(e) {
    const url = e.currentTarget.dataset.url;
    wx.navigateTo({ url });
  },

  goToChat() {
    wx.switchTab({ url: '/pages/chat/chat' });
  },
});