// pages/finance/finance.js
const api = require('../../utils/api');

Page({
  data: {
    stats: null,
    records: [],
    loading: false,
    showAdd: false,
    newRecord: { type: 'expense', amount: '', category: '', note: '', record_date: '' },
  },

  onShow() {
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1;
      const [stats, records] = await Promise.all([
        api.getFinanceStats(year, month),
        api.getFinanceRecords(year, month),
      ]);
      this.setData({ stats, records, loading: false });
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  showAddModal() {
    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    this.setData({ showAdd: true, 'newRecord.record_date': dateStr });
  },

  async onAddRecord() {
    if (!this.data.newRecord.amount) {
      wx.showToast({ title: '请输入金额', icon: 'none' });
      return;
    }
    try {
      await api.createFinanceRecord({
        ...this.data.newRecord,
        amount: parseFloat(this.data.newRecord.amount),
      });
      this.setData({ showAdd: false });
      wx.showToast({ title: '添加成功', icon: 'success' });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '添加失败', icon: 'none' });
    }
  },

  categoryMap: {
    'food': '餐饮', 'transport': '交通', 'shopping': '购物', 'entertainment': '娱乐',
    'health': '健康', 'education': '教育', 'housing': '住房', 'utility': '水电',
    'vehicle': '车辆', 'social': '社交', 'other': '其他',
  },

  getCategoryName(cat) {
    return this.categoryMap[cat] || cat || '未分类';
  },
});