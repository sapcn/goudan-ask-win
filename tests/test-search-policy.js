#!/usr/bin/env node
// 联网搜索判定的回归网。
//
// 定型原则（Jane 2026-08-02 反馈「让它去搜索，还是回答我不能搜索」后重写）：
//   - 秒查划词默认不联网 —— 她要的是结合眼前画面解释，不是搜索结果
//   - 她自己打字说要搜 → 一律联网。宁可多搜不可漏：漏了她收到一句
//     「我不能搜索」，那是最糟体验；多搜只是慢一点、多花几厘钱。
//
// 旧版是**整词枚举**（`帮我搜索|搜索一下|搜一下`…），「去搜索」「联网搜索」
// 「search」这些同样自然的说法一个都没枚举到 → 工具没挂上 → 模型老实回
// 「我不能搜索」。别再退回枚举式写法。
const assert = require("assert");
const p = require("../webview/search-policy.js");

const shouldSearch = [
  "去搜索", "联网搜索", "搜索一下", "帮我搜一下", "搜搜看", "搜个资料",
  "你去查查", "帮我查一下", "查证一下", "谷歌一下", "google 一下",
  "search this", "look up this", "网上找找", "在线找找", "看看官网怎么说",
  "最新消息是什么", "现在多少钱", "今天的行情", "最近发布了吗",
];
const shouldNotSearchInLookup = [
  "解释〔TTL〕", "这个什么意思", "这段话啥意思", "为什么这么设计",
  "帮我翻译一下", "怎么理解这个架构", "总结一下这段",
];

for (const q of shouldSearch) {
  assert.strictEqual(p.shouldUseGoogleSearch(q, { lookupMode: false }), true,
    `「${q}」应该联网`);
  // 明确的搜索指令在秒查模式下也必须生效——explicit 永远压过 explanation
  assert.strictEqual(p.shouldUseGoogleSearch(q, { lookupMode: true }), true,
    `「${q}」在秒查模式下也应该联网`);
}
for (const q of shouldNotSearchInLookup) {
  assert.strictEqual(p.shouldUseGoogleSearch(q, { lookupMode: true }), false,
    `秒查模式下「${q}」不该联网`);
}
assert.strictEqual(p.shouldUseGoogleSearch("", { lookupMode: false }), false, "空问题不联网");

// 兜底文案：万一还是漏了某种说法，不能只撂一句「我不能搜索」
const prompts = require("fs").readFileSync(
  require("path").join(__dirname, "../webview/prompts.js"), "utf8");
assert.ok(prompts.includes("我不能搜索"),
  "对话提示词必须处理「需要联网但没工具」的情况，别让它撂一句就完事");
assert.ok(prompts.includes("搜索一下"),
  "兜底时要告诉 Jane 怎么手动触发联网");

console.log(`search-policy: ${shouldSearch.length + shouldNotSearchInLookup.length + 1} passed`);
