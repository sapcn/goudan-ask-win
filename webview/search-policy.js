// 什么时候给 Gemini 挂 google_search 工具。
//
// 定型原则（2026-08-02，Jane 反馈「让它去搜索，还是回答我不能搜索」后重写）：
//   - **秒查划词**默认不联网：她要的是「结合眼前画面解释这个词」，不是搜索结果。
//   - **她自己打字**说要搜 → 一律联网，宁可多搜不可漏。漏了的代价是模型回一句
//     「我不能搜索」，那是最糟的体验；多搜一次只是慢一点、多花几厘钱。
//
// 旧版失败原因：explicit 正则是**整词枚举**（`帮我搜索|搜索一下|搜一下`…），
// 「去搜索」「联网搜索」「search」这类同样自然的说法一个都没枚举到 → 工具没挂上
// → 模型老实回「我不能搜索」。现在改成「动词字根 + 上下文」组合，覆盖面大得多。
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.XiaoerSearchPolicy = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  // 明确的搜索意图。按「字根」匹配而不是枚举整句，别再漏。
  const explicit = new RegExp([
    "搜索", "搜一?下", "搜搜", "去搜", "帮我搜", "搜个",          // 搜
    "查一?下", "查查", "帮我查", "查询", "去查", "查证", "核实",   // 查
    "联网", "上网", "网上", "在线找", "找找看",                   // 联网
    "谷歌", "google", "search", "look\\s*up", "web\\s*search",    // 英文/品牌
    "最新消息", "官网怎么说", "有没有新的",
  ].join("|"), "i");

  // 时效性问题：答案会随时间变，靠模型记忆一定过时 → 该联网。
  const fresh = /(今天|今日|昨天|现在|当前|目前|最新|最近|刚发布|刚出|实时|现价|价格|多少钱|报价|收费|汇率|天气|新闻|版本号|更新日志|热搜|票房|比分|股价|行情|政策|发布了吗|上线了吗|还在吗)/i;

  // 「解释类」问题：她要的是理解眼前的东西，不是搜网页。
  // 只在秒查模式下用来压制 fresh 的误触发；**永远压不过 explicit**。
  const explanation = /(解释|什么意思|啥意思|含义|这句话|这一段|这个词|总结|概括|为什么|怎么理解|如何理解|翻译)/i;

  function shouldUseGoogleSearch(question, options) {
    const q = String(question || "").trim();
    if (!q) return false;
    // 1. 她明说要搜 → 无条件联网，任何模式都不拦
    if (explicit.test(q)) return true;
    // 2. 秒查模式下的解释类提问 → 不联网（这是秒查的本分）
    if (options && options.lookupMode && explanation.test(q)) return false;
    // 3. 时效性问题 → 联网
    return fresh.test(q);
  }

  return { shouldUseGoogleSearch };
});
