// pages/anniversary/anniversary.js
const api = require('../../utils/api');

Page({
  data: {
    anniversaries: [],
    wishList: [],
    loading: false,
    showAdd: false,
    showWish: false,
    newAnniversary: { name: '', date: '', reminder_days: 7 },
    newWish: { content: '', category: '' },
  },

  onShow() {
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [anniversaries, wishList] = await Promise.all([
        api.getAnniversaries(),
        api.getWishList(),
      ]);
      this.setData({ anniversaries, wishList, loading: false });
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  showAddModal() {
    this.setData({ showAdd: true, newAnniversary: { name: '', date: '', reminder_days: 7 } });
  },

  async onAdd() {
    if (!this.data.newAnniversary.name || !this.data.newAnniversary.date) {
      wx.showToast({ title: '请填写完整信息', icon: 'none' });
      return;
    }
    try {
      await api.createAnniversary(this.data.newAnniversary);
      this.setData({ showAdd: false });
      wx.showToast({ title: '添加成功', icon: 'success' });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '添加失败', icon: 'none' });
    }
  },

  async onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除',
      content: '确定删除这个纪念日？',
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.deleteAnniversary(id);
            wx.showToast({ title: '已删除', icon: 'success' });
            this.loadData();
          } catch (e) {
            wx.showToast({ title: '删除失败', icon: 'none' });
          }
        }
      },
    });
  },

  showWishModal() {
    this.setData({ showWish: true, newWish: { content: '', category: '' } });
  },

  async onAddWish() {
    if (!this.data.newWish.content) {
      wx.showToast({ title: '请输入愿望内容', icon: 'none' });
      return;
    }
    try {
      await api.addWishItem(this.data.newWish);
      this.setData({ showWish: false });
      wx.showToast({ title: '添加成功', icon: 'success' });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '添加失败', icon: 'none' });
    }
  },

  getDaysUntil(dateStr) {
    const today = new Date();
    const target = new Date(dateStr);
    target.setFullYear(today.getFullYear());
    if (target < today) target.setFullYear(today.getFullYear() + 1);
    const diff = Math.ceil((target - today) / (1000 * 60 * 60 * 24));
    return diff;
  },
});