// pages/chat/chat.js
const api = require('../../utils/api');

Page({
  data: {
    messages: [
      { role: 'bot', content: '你好！我是家庭备忘录助手。你可以跟我说：\n• "下周三交电费"\n• "买牛奶"\n• "今天加油花了300"\n• "记一下结婚纪念日"\n• "这月花了多少钱"', time: '' },
    ],
    inputValue: '',
    sending: false,
    hasFamily: false,
  },

  onShow() {
    const app = getApp();
    this.setData({ hasFamily: app.globalData.hasFamily });
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  async sendMessage() {
    const msg = this.data.inputValue.trim();
    if (!msg || this.data.sending) return;

    // 检查是否已加入家庭
    const app = getApp();
    if (!app.globalData.hasFamily) {
      wx.showToast({ title: '请先加入家庭空间', icon: 'none' });
      return;
    }

    this.setData({ inputValue: '', sending: true });

    // 添加用户消息
    const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    this.data.messages.push({ role: 'user', content: msg, time: now });
    this.setData({ messages: this.data.messages });

    try {
      const res = await api.sendMessage(msg);
      const replyTime = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      this.data.messages.push({ role: 'bot', content: res.reply, time: replyTime, needConfirm: res.need_confirm });
      this.setData({ messages: this.data.messages });
    } catch (e) {
      this.data.messages.push({ role: 'bot', content: '抱歉，处理时出了点问题，请稍后重试。', time: '' });
      this.setData({ messages: this.data.messages });
    }

    this.setData({ sending: false });
    this.scrollToBottom();
  },

  scrollToBottom() {
    setTimeout(() => {
      wx.createSelectorQuery().select('#chat-list').boundingClientRect(rect => {
        wx.pageScrollTo({ scrollTop: rect.height });
      }).exec();
    }, 100);
  },
});