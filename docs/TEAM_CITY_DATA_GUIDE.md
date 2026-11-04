# TravelMate 队友同步与城市景点数据导入指南

本文给没有开发经验的队友使用。当前项目允许在不同电脑上继续增加城市景点数据，但必须遵守“先同步、再分支、后合并”的流程。

## 一、先说结论

可以。队友拉取最新代码后，可以继续增加杭州、重庆、南京等城市的景点数据。

当前推荐的数据文件是：

- `data/core_attractions.json`：已经提交到仓库的景点名称、简介、城市、分类和图片 URL；
- `scripts/rebuild_core_attractions.py`：从 JSON 重建本地 SQLite 数据库；
- `scripts/fetch_real_images.py`：为缺少真实图片的景点从 Wikimedia Commons 查询图片；
- `database/travelmate.db`：本地生成文件，不提交到 Git，也不通过 Git 同步。

队友不需要手动复制数据库文件。每台电脑都应从仓库代码和 JSON 数据生成自己的本地数据库。

## 二、在 VS Code 中同步我的最新代码和数据

### 1. 第一次使用

在 VS Code 中打开终端，执行：

```powershell
git clone https://gitee.com/letsgo225/TravelMate.git
cd TravelMate
code .
```

### 2. 已经有旧项目

先关闭正在运行的 Flask 和 cpolar，再在 VS Code 终端执行：

```powershell
git switch master
git pull origin master
```

如果提示有本地修改，不要直接覆盖。先执行：

```powershell
git status
```

把自己的修改备份到单独文件夹，或联系成员 A 处理。不要使用 `git reset --hard`。

### 3. 创建 Python 环境并安装依赖

Windows + VS Code 推荐执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果 PowerShell 不允许激活环境，可以直接使用项目解释器：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

在 VS Code 中按 `Ctrl+Shift+P`，选择 **Python: Select Interpreter**，选择：

```text
TravelMate\.venv\Scripts\python.exe
```

## 三、给 DeepSeek 4.1 Flash 的标准指令词

每位队友都应该把下面的指令复制给自己的 Agent，然后只替换城市名称。

```text
你现在负责 TravelMate 项目的城市景点数据导入。

项目规则：
1. 这是 Flask + SQLite 项目，数据库使用本地 database/travelmate.db。
2. 当前项目已经有 data/core_attractions.json、scripts/rebuild_core_attractions.py
   和 scripts/fetch_real_images.py。
3. 不要修改用户认证、收藏、行程、前端无关模块。
4. 不要上传 database/travelmate.db、真实用户信息、密码、API Key 或 cpolar token。
5. 不要切换到其他 Git 分支，不要 push；我会先检查结果再提交。
6. 所有新增景点必须有 name、description、image_url、city、category_slug。
7. 每个城市录入 20 个最核心、最著名、游客最可能游览的景点。
8. description 写 80-150 字中文简介，不要编造具体票价、营业时间或未经确认的历史事实。
9. image_url 必须是可访问的 JPG、JPEG 或 PNG 直链；优先使用 Wikimedia Commons。
10. 找不到可靠图片时使用 /static/images/placeholder-attraction.svg。
11. 景点名称不能使用“景点1”“某某遗址01”等无意义名称，也不要重复。

本次只处理：<城市名>

请按以下顺序工作：
1. 先检查当前分支、git status、现有数据文件和脚本。
2. 在 data/core_attractions.json 中增加这个城市的 20 条核心景点。
3. 保留其他城市数据，不要删除或重写其他人的记录。
4. 执行必要的数据格式检查。
5. 执行 python -m scripts.rebuild_core_attractions 重建本地数据库。
6. 如果有占位图，执行 python -m scripts.fetch_real_images 重新获取图片。
7. 用接口或 SQLite 查询确认该城市正好有 20 条，四个核心字段都不为空。
8. 运行 pytest -q。
9. 最后只汇报修改文件、城市数量、真实图片数量、测试结果和仍需人工检查的问题。
```

如果 Agent 建议直接修改数据库而不是修改 JSON，应回复：

```text
不要直接把数据库文件作为成果提交。请把可同步的数据写入 data/core_attractions.json，
数据库只作为本地验证结果，然后重新运行 scripts.rebuild_core_attractions.py。
```

## 四、建议新增城市清单

六城核心数据已经完成。后续只增加全国主要城市，不建议一次导入过多小城市。

推荐清单：

- 华北：天津、秦皇岛、太原、呼和浩特
- 东北：沈阳、大连、长春、哈尔滨
- 华东：杭州、南京、苏州、无锡、宁波、厦门、福州、济南、青岛
- 华中：武汉、长沙、郑州、南昌
- 华南：珠海、佛山、海口、三亚
- 西南：重庆、昆明、贵阳、拉萨
- 西北：乌鲁木齐、兰州、银川

如果时间有限，优先完成：

```text
杭州、重庆、南京、武汉、青岛、厦门、三亚、昆明、大连、哈尔滨
```

每个城市建议 20 条，优先保证城市代表性，不要为了数量导入普通商场、酒店、公交站或无明确旅游价值的设施。

## 五、三种团队分工方案

### 方案 A：两个人

适合只有两位队友能够稳定操作电脑的情况。

**成员 1：华东和华北**

- 天津
- 杭州
- 南京
- 苏州
- 济南
- 青岛
- 大连

**成员 2：华中、华南、西南和西北**

- 重庆
- 武汉
- 长沙
- 厦门
- 三亚
- 昆明
- 哈尔滨

每人建议先处理 5—7 个城市，完成一个城市就提交一次分支，不要一次修改全部城市。

### 方案 B：三个人

适合三位队友分别使用自己的电脑。

**成员 1：北方和东北**

- 天津
- 秦皇岛
- 太原
- 沈阳
- 大连
- 长春
- 哈尔滨

**成员 2：华东和华中**

- 杭州
- 南京
- 苏州
- 宁波
- 济南
- 青岛
- 武汉
- 长沙

**成员 3：华南、西南和西北**

- 重庆
- 厦门
- 福州
- 三亚
- 昆明
- 贵阳
- 拉萨
- 兰州

### 方案 C：四个人

适合希望并行速度最快、且成员 A 能及时审核合并的情况。

**成员 1：华北**

- 天津
- 秦皇岛
- 太原
- 呼和浩特

**成员 2：东北和山东**

- 沈阳
- 大连
- 长春
- 哈尔滨
- 济南
- 青岛

**成员 3：华东和华中**

- 杭州
- 南京
- 苏州
- 无锡
- 宁波
- 武汉
- 长沙

**成员 4：华南、西南、西北**

- 重庆
- 厦门
- 三亚
- 昆明
- 贵阳
- 拉萨
- 兰州

重要：同一城市只能分配给一个人，同一时间不要让两个人编辑同一个城市。

## 六、每个队友完成后的本地检查

### 1. 检查 JSON 数量

将 `<城市名>` 替换为自己的城市，例如 `杭州`：

```powershell
.\.venv\Scripts\python.exe -c "import json; rows=json.load(open('data/core_attractions.json', encoding='utf-8')); city='杭州'; print(city, sum(x['city'] == city+'市' for x in rows))"
```

结果应该是 20。

### 2. 重建本地数据库

```powershell
.\.venv\Scripts\python.exe -m scripts.rebuild_core_attractions
```

### 3. 检查接口

先启动应用：

```powershell
.\.venv\Scripts\python.exe app.py
```

浏览器打开：

```text
http://127.0.0.1:5000/attractions?city=杭州
```

也可以在终端测试接口：

```powershell
curl "http://127.0.0.1:5000/api/attractions?city=%E6%9D%AD%E5%B7%9E&page_size=30"
```

检查以下内容：

- 总数量是否为 20；
- 每张卡片是否有名称；
- 每张卡片是否有简介；
- 每张卡片是否有图片；
- 城市筛选是否只显示当前城市；
- 关键词搜索是否有效；
- 点击景点详情是否正常。

### 4. 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试必须全部通过。不能删除测试、屏蔽异常或降低检查标准。

## 七、队友如何提交和同步数据

每位队友完成一个城市后，在自己的分支提交：

```powershell
git switch -c feature/city-hangzhou
git add data/core_attractions.json
git add scripts/rebuild_core_attractions.py
git add tests
git commit -m "feat: add Hangzhou core attractions"
git push -u origin feature/city-hangzhou
```

如果多个城市一起完成，请把城市名称写进提交信息，例如：

```powershell
git commit -m "feat: add Hangzhou and Chongqing attractions"
```

然后把以下信息发给成员 A：

```text
我完成了：<城市名>
分支：feature/city-<city>
景点数量：20
真实图片数量：多少
占位图数量：多少
pytest：通过/失败
提交号：<commit hash>
```

## 八、成员 A 合并队友成果

成员 A 先同步自己的 master：

```powershell
git switch master
git pull origin master
```

查看队友分支：

```powershell
git fetch origin
git branch -r
```

合并一个队友分支：

```powershell
git merge --no-ff origin/feature/city-hangzhou
```

合并后必须重新验证：

```powershell
.\.venv\Scripts\python.exe -m scripts.rebuild_core_attractions
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status
```

确认无误后再推送：

```powershell
git push origin master
```

队友随后同步：

```powershell
git switch master
git pull origin master
.\.venv\Scripts\python.exe -m scripts.rebuild_core_attractions
```

## 九、最重要的协作规则

1. 不要提交 `database/travelmate.db`。
2. 不要提交真实用户信息、密码、密钥或 cpolar token。
3. 不要多人同时编辑同一个城市。
4. 不要把图片下载到仓库，仓库只保存图片 URL。
5. 不要直接修改数据库作为唯一成果，必须更新 JSON。
6. 合并前必须运行测试和城市数量检查。
7. 如果发生 JSON 冲突，停止编辑并联系成员 A，不要随意选择一方覆盖。
8. 每次只合并一个队友分支，出现问题容易回退和定位。
