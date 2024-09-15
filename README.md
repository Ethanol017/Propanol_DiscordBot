# 丙醇機器人 Propanol DiscordBot
這是一個用Discord.py寫的機器人，服務於我私人的伺服器。

## Cogs
#### ARK
使用Discord指令來開啟ARK遊戲伺服器。 </br>
因為機器人跟遊戲伺服器運行於同一linux主機，所以才能實現這個功能，Windows可能要找其他方法，使用了python庫subprocess 跟 [ark-server-tools](https://github.com/arkmanager/ark-server-tools) 實現

#### 動態語音
實現了動態語音頻道的創建與刪除，以及每個人可以訂閱其他人，當有人創建語音時可以自動通知 @訂閱者。
因為只服務單一伺服器，所以需要手動在 config.ini 中填入 __語音入口ID__ 和 __通知頻道ID__。

#### 自訂機器人活動
使用指令修該改機器人名字底下的活動自訂義修改，添加了復原機制，重啟機器人後會自動復原活動。

## 其他指令
#### 加載Cog
實現了在機器人啟動狀態下自動尋找到Cogs資料夾內的cog，並做成Discord選擇框，以方便加載、卸載、重載。
#### sync
https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html

## 待作清單
- [ ]  動態語音刪除時，將語音聊天室以討論串的方式存到其他頻道
- [ ]  添加隨機自訂狀態 (隨機清單添加指令已完成)
