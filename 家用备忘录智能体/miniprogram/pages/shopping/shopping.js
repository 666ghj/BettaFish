// pages/shopping/shopping.js
const api = require('../../utils/api');

Page({
  data: {
    tabs: ['家用', '老公', '老婆'],
    activeTab: 0,
    items: [],
    loading: false,
    showAdd: false,
    newItem: { name: '', list_type: 'household', estimated_price: '', purchase_reason: '' },
    subTabs: ['全部', '待购买', '已购买'],
    subActive: 0,
  },

  onShow() {
    this.loadItems();
  },

  async loadItems() {
    this.setData({ loading: true });
    try {
      const listTypes = ['household', 'husband', 'wife'];
      const listType = listTypes[this.data.activeTab];
      const statusMap = ['', 'pending', 'bought'];
      const status = statusMap[this.data.subActive] || '';

      const items = await api.getShoppingItems(listType, status);
      this.setData({ items, loading: false });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  onTabChange(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ activeTab: parseInt(index) }, () => this.loadItems());
  },

  onSubTabChange(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ subActive: parseInt(index) }, () => this.loadItems());
  },

  showAddModal() {
    const listTypes = ['household', 'husband', 'wife'];
    this.setData({
      showAdd: true,
      'newItem.list_type': listTypes[this.data.activeTab],
    });
  },

  async onAddItem() {
    if (!this.data.newItem.name) {
      wx.showToast({ title: '请输入物品名称', icon: 'none' });
      return;
    }
    try {
      await api.createShoppingItem(this.data.newItem);
      this.setData({ showAdd: false, 'newItem.name': '', 'newItem.estimated_price': '', 'newItem.purchase_reason': '' });
      wx.showToast({ title: '添加成功', icon: 'success' });
      this.loadItems();
    } catch (e) {
      wx.showToast({ title: '添加失败', icon: 'none' });
    }
  },

  async onAgree(e) {
    const id = e.currentTarget.dataset.id;
    const agreed = e.currentTarget.dataset.agreed === 'true';
    try {
      await api.agreeShoppingItem(id, !agreed);
      this.loadItems();
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' });
    }
  },

  async onPurchase(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '标记已购买',
      content: '确认已购买？将自动记录到家庭收支。',
      success: async (res) => {
        if (res.confirm) {
          try {
            const now = new Date();
            const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
            await api.purchaseShoppingItem(id, { actual_price: 0, purchase_method: '', purchase_date: dateStr });
            wx.showToast({ title: '已记录', icon: 'success' });
            this.loadItems();
          } catch (e) {
            wx.showToast({ title: '操作失败', icon: 'none' });
          }
        }
      },
    });
  },
});