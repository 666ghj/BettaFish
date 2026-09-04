// pages/payment/payment.js
const api = require('../../utils/api');

Page({
  data: {
    items: [],
    records: [],
    loading: false,
  },

  onShow() {
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const items = await api.getPaymentItems();
      this.setData({ items, loading: false });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  async onMarkPaid(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '标记已缴费',
      content: '确认已缴纳？',
      success: async (res) => {
        if (res.confirm) {
          try {
            const now = new Date();
            const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
            await api.createPaymentRecord({ payment_item_id: id, actual_amount: 0, paid_date: dateStr });
            wx.showToast({ title: '已记录', icon: 'success' });
            this.loadData();
          } catch (e) {
            wx.showToast({ title: '操作失败', icon: 'none' });
          }
        }
      },
    });
  },
});