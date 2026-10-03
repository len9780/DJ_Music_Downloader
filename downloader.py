import glob
import json
import os
import subprocess
import time

# ==================== 🛠️ 核心全域設定 ====================
openvpn_command = "openvpn"
CONFIG_FILE = "config.json"
# ===============================================================


def load_config():
    """讀取 json 設定檔，若不存在則自動產生一個支援多網址 YouTube 的預設範本"""
    default_config = {
        "openvpn_setting": {"url": "usa_free_network.ovpn", "enable": True},
        "create_graph_setting": {"enable": True},
        "spotify_task": {
            "url": "https://spotify.com",
            "enable": False,
        },
        "soundcloud_task": {
            "url": "https://soundcloud.com",
            "enable": False,
        },
        "youtube_task": {
            "urls": ["https://youtube.com"],
            "enable": True,
        },
    }

    if not os.path.exists(CONFIG_FILE):
        print(f"📝 找不到設定檔，已為您自動產生預設的 {CONFIG_FILE}")
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 讀取 {CONFIG_FILE} 失敗，格式可能有錯。將使用預設設定執行。原因: {e}")
        return default_config


def find_last_downloaded_file():
    """自動尋找當前資料夾下最新產生的音訊檔案名稱"""
    files = glob.glob("*.*")
    audio_files = [
        f
        for f in files
        if f.lower().endswith((".mp3", ".m4a", ".opus", ".wav", ".flac"))
    ]
    if not audio_files:
        return None
    return max(audio_files, key=os.path.getmtime)


def create_graph(audio_path, graph_enable):
    """根據 JSON 開關決定是否為下載回來的音檔繪製頻譜圖"""
    if not graph_enable:
        return

    if not audio_path or not os.path.exists(audio_path):
        print("⚠️ 找不到對應的音訊檔案，無法產生頻譜圖。")
        return

    base_name, _ = os.path.splitext(audio_path)
    output_png = f"{base_name}_spectrum.png"

    print(f"  └─ 📊 正在生成音訊頻譜圖...")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                audio_path,
                "-lavfi",
                "showspectrumpic=s=1024x512:legend=1",
                output_png,
                "-y",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"  └─ 🎉 頻譜圖輸圖成功: {output_png}")
    except subprocess.CalledProcessError:
        print(f"  └─ ❌ 頻譜圖轉換失敗")


def download_like_website(spotify_url, graph_enable):
    sync_file = "my_playlist.spotdl"
    success_list = []
    failed_list = []

    print("\n📋 正在使用同步通道提取你的公開歌單歌曲明細...")

    try:
        subprocess.run(
            ["spotdl", "sync", spotify_url, "--save-file", sync_file],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        print(
            "❌ 依然讀取失敗。這代表 Spotify 官方對你目前 IP 的匿名請求进行了封鎖。"
        )
        return

    if not os.path.exists(sync_file):
        print("❌ 提取歌單失敗。")
        return

    with open(sync_file, "r", encoding="utf-8") as f:
        playlist_data = json.load(f)

    songs = playlist_data.get("songs", [])
    total_songs = len(songs)
    print(f"🎵 成功偵測到 {total_songs} 首歌曲，開始逐一下載統計...\n")

    for index, track in enumerate(songs, start=1):
        song_query = f"{track.get('name')} - {', '.join(track.get('artists', []))}"
        print(f"[{index}/{total_songs}] 正在下載: {song_query}...")

        try:
            subprocess.run(
                [
                    "spotdl",
                    "download",
                    song_query,
                    "--format",
                    "mp3",
                    "--bitrate",
                    "320k",
                    "--audio",
                    "youtube-music",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            print("  └─ ✅ 下載成功！")
            success_list.append(song_query)

            downloaded_file = find_last_downloaded_file()
            create_graph(downloaded_file, graph_enable)

        except subprocess.CalledProcessError as e:
            print("  └─ ❌ 下載失敗！")
            error_msg = (
                e.stderr.strip().split("\n")[-1] if e.stderr else "未知"
            )
            failed_list.append(f"{song_query} -> {error_msg}")

    if os.path.exists(sync_file):
        os.remove(sync_file)

    print("\n" + "=" * 50)
    print("📊 Spotify 播放清單下載任務總結報告")
    print("=" * 50)
    print(
        f"📈 總歌曲數: {total_songs} | 🎉 成功: {len(success_list)} | 🚨 失敗: {len(failed_list)}"
    )
    if failed_list:
        print("\n🔴 【下載失敗明細】:")
        for idx, f_song in enumerate(failed_list, 1):
            print(f"  {idx}. {f_song}")
    print("=" * 50)


def download_soundcloud_max_quality(soundcloud_url, vpn_config, graph_enable):
    vpn_process = None
    target_ovpn = vpn_config.get("url", "usa_free_network.ovpn")
    vpn_enable = vpn_config.get("enable", False)

    if vpn_enable:
        if os.path.exists(target_ovpn):
            print(
                f"\n💡 設定檔已啟用 OpenVPN，將載入 [{target_ovpn}] 進行跨區下載..."
            )
            try:
                vpn_process = subprocess.Popen(
                    [openvpn_command, "--config", target_ovpn],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print("⏳ 正在建立安全跨區隧道，請稍候 20 秒...")
                time.sleep(20)
                print("🌐 跨區連線成功！整台電腦已切換至歐美免費網路。")
            except Exception as e:
                print(f"⚠️ 啟動 VPN 時發生未知錯誤: {e}。轉為無 VPN 模式。")
                vpn_process = None
        else:
            print(
                f"\n⚠️ JSON 雖然開啟了 VPN，但找不到檔案 [{target_ovpn}]！轉為無 VPN 模式。"
            )
    else:
        print("\nℹ️  JSON 設定已關閉 VPN 功能。轉為無 VPN 模式。")

    try:
        print(
            f"🚀 正在分析並抓取 SoundCloud 最高音質原始串流: {soundcloud_url}"
        )
        cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--embed-metadata",
            # 進階解析：確保將 SoundCloud 上傳者寫入音樂的 Artist 欄位中
            "--parse-metadata", "uploader:%(meta_artist)s",
            soundcloud_url,
        ]
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print("🎉 下載成功！已儲存為高品質原始 M4A 檔案。")

        downloaded_file = find_last_downloaded_file()
        create_graph(downloaded_file, graph_enable)

    except subprocess.CalledProcessError as e:
        print(f"❌ 下載失敗: {e.stderr}")
    except Exception as e:
        print(f"❌ 發生未知錯誤: {e}")
    finally:
        if vpn_process:
            print("🔌 下載任務結束，正在自動關閉 OpenVPN 隧道...")
            vpn_process.terminate()
            vpn_process.wait()
            print("✅ 網路已安全回復為原本的本地連線。")


def download_youtube_highest_audio(youtube_url, graph_enable):
    """處理單首 YouTube 下載的核心函式"""
    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "--embed-metadata",
        # 進階解析：將 YouTube 上傳頻道解析為 Artist；如果有播放清單名稱，則將其解析為 Album 欄位
        "--parse-metadata", "uploader:%(meta_artist)s",
        "--parse-metadata", "playlist_title:%(meta_album)s",
        youtube_url,
    ]
    try:
        # 改為背景擷取輸出，保持終端機乾淨
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print("  └─ ✅ 下載成功！已儲存為原始最高規格 M4A 音檔。")

        # 抓取最新檔案並畫圖
        downloaded_file = find_last_downloaded_file()
        create_graph(downloaded_file, graph_enable)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  └─ ❌ 下載失敗: {e.stderr.strip().split('\n')[-1]}")
        return False


# ==================== 🎵 任務執行區 ====================
if __name__ == "__main__":
    config = load_config()

    vpn_setting_block = config.get(
        "openvpn_setting", {"url": "usa_free_network.ovpn", "enable": False}
    )
    graph_enable = config.get("create_graph_setting", {}).get("enable", True)

    # 執行 Spotify 任務
    if config.get("spotify_task", {}).get("enable", False):
        spotify_url = config["spotify_task"]["url"]
        download_like_website(spotify_url, graph_enable)
    else:
        print("ℹ️  設定檔中 Spotify 下載已關閉，跳過該任務。")

    # 執行 SoundCloud 任務
    if config.get("soundcloud_task", {}).get("enable", False):
        soundcloud_url = config["soundcloud_task"]["url"]
        download_soundcloud_max_quality(
            soundcloud_url, vpn_setting_block, graph_enable
        )
    else:
        print("ℹ️  設定檔中 SoundCloud 下載已關閉，跳過該任務。")

    # 💡 核心修改：執行 YouTube 多網址循環任務
    if config.get("youtube_task", {}).get("enable", False):
        youtube_urls = config["youtube_task"].get("urls", [])
        total_yt = len(youtube_urls)

        if total_yt > 0:
            print(f"\n🚀 偵測到共有 {total_yt} 首 YouTube 網址，開始批次下載任務...")
            for idx, yt_url in enumerate(youtube_urls, start=1):
                print(f"[{idx}/{total_yt}] 正在提取音軌: {yt_url}")
                download_youtube_highest_audio(yt_url, graph_enable)
        else:
            print("⚠️ YouTube 任務已開啟，但在 'urls' 清單內沒發現任何網址。")
    else:
        print("ℹ️  設定檔中 YouTube 下載已關閉，跳過該任務。")
