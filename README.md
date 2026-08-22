# 关键词出牌插件

根据消息中的卡牌名称发送对应卡面。内置两个彼此独立的游戏卡组：

- `sts`：Slay the Spire /《杀戮尖塔》，367 张卡牌。
- `sts2`：Slay the Spire 2 /《杀戮尖塔 2》，1,151 张半尺寸卡面；静态卡为 PNG，动画卡为 WebP。

## 配置

在 AstrBot WebUI 的插件配置中设置：

- `session_whitelist`：允许触发插件的会话 ID。
- `case_sensitive`：匹配英文关键字时是否区分大小写。
- `keyword_ratio_trigger`：开启后按“命中关键字长度 ÷ 消息长度”限制触发。占比不超过 15% 时不发送，达到 50% 时必定发送；中间按线性概率发送。例如占比 32.5% 时发送概率为 50%。计算时忽略消息首尾空白，内部空格及标点仍计入消息长度。默认关闭，以保持原有的“匹配即发送”行为。
- `enabled_decks`：启用的卡组 ID，例如 `["sts", "sts2"]`；填写 `["*"]` 启用全部已发现卡组。
- `deck_priority`：卡组匹配顺序。例如 `["sts2", "sts"]` 会优先匹配 StS2；未写入此列表但已启用的卡组会按 ID 排序追加到末尾。

优先级先按卡组比较，再在同一卡组内优先匹配更长、更具体的关键字。同一关键字对应多张卡时随机选择一张。

## 添加其他游戏卡组

在 `decks/` 下新建以卡组 ID 命名的目录：

```text
decks/example/
├─ deck.json
├─ card_dict.py
└─ cards/
   └─ ExampleCard.png
```

`deck.json`：

```json
{
  "id": "example",
  "name": "Example Game",
  "dictionary": "card_dict.py",
  "cards": "cards"
}
```

`card_dict.py`：

```python
card_dict = {
    "ExampleCard": ["Example Card", "ExampleCard", "示例卡牌"],
}
```

字典 key 必须等于图片去掉路径和扩展名后的文件名。图片目录可以继续划分子目录，但整个卡组内不得出现相同的文件名 stem。支持 PNG、WebP、GIF、JPG 和 JPEG。添加后，在 `enabled_decks` 中启用该 ID，并按需加入 `deck_priority`。

## 字典说明

内置 StS 与 StS2 字典的每张卡最多保留三个标准关键字：英文名、移除空格后的英文名、中文名；重复项只保留一次。升级版 StS2 卡牌使用 `+`，不使用单词 `Plus`。

## 资源说明

游戏卡面、名称及相关素材的权利归各自权利人所有。本插件与 Mega Crit Games 无隶属或认可关系，请仅在符合法律和资源授权条件的场景中使用。
