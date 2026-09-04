// pages/vehicle/vehicle.js
const api = require('../../utils/api');

Page({
  data: {
    vehicle: null,
    expenses: [],
    license: [],
    loading: false,
    showEdit: false,
    showExpense: false,
    editForm: {},
    expenseForm: { expense_type: 'fuel', amount: '', date: '', location: '' },
    tabs: ['信息', '支出', '驾驶分'],
    activeTab: 0,
  },

  onShow() {
    this.loadData();
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [vehicle, expenses, license] = await Promise.all([
        api.getVehicleInfo(),
        api.getVehicleExpenses(),
        api.getDrivingLicense(),
      ]);
      this.setData({ vehicle, expenses, license, loading: false });
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  onTabChange(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ activeTab: parseInt(index) });
  },

  showEditModal() {
    const v = this.data.vehicle || {};
    this.setData({
      showEdit: true,
      editForm: {
        brand: v.brand || '',
        model: v.model || '',
        plate_number: v.plate_number || '',
        insurance_expire: v.insurance_expire || '',
        next_maintenance_date: v.next_maintenance_date || '',
        next_inspection_date: v.next_inspection_date || '',
        insurance_company: v.insurance_company || '',
        maintenance_shop: v.maintenance_shop || '',
        maintenance_phone: v.maintenance_phone || '',
      },
    });
  },

  async onSaveVehicle() {
    try {
      await api.updateVehicleInfo(this.data.editForm);
      this.setData({ showEdit: false });
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    }
  },

  showExpenseModal() {
    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    this.setData({ showExpense: true, 'expenseForm.date': dateStr });
  },

  async onAddExpense() {
    if (!this.data.expenseForm.amount) {
      wx.showToast({ title: '请输入金额', icon: 'none' });
      return;
    }
    try {
      await api.createVehicleExpense({
        ...this.data.expenseForm,
        amount: parseFloat(this.data.expenseForm.amount),
      });
      this.setData({ showExpense: false });
      wx.showToast({ title: '记录成功', icon: 'success' });
      this.loadData();
    } catch (e) {
      wx.showToast({ title: '记录失败', icon: 'none' });
    }
  },

  expenseTypeMap: {
    'fuel': '加油', 'charging': '充电', 'insurance': '保险',
    'violation': '违章', 'maintenance': '保养', 'other': '其他',
  },
});