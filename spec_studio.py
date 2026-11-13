
# [稼働Ver 作業版 Rev.2] 3フェーズ分割生成アーキテクチャ(MAX_TOKENS物理上限対策)、タイムアウト75秒最適化、全8章完全性自動監査(欠落上書き完全防止)、生成進行度UI可視化
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpecStudio: 現場設計書ダッシュボード自動作成システム
Version: 1.0.0 (正式リリース版・3フェーズ分割生成・全8章完全性監査・2段階モデル自動フォールバック搭載)
- 外部ライブラリ依存ゼロ (Python標準ライブラリのみで動作)
- 127.0.0.1 限定バインド ＆ x-goog-api-key ヘッダー認証
- 【3フェーズ分割生成】MAX_TOKENS(8192)物理上限を根本回避し、第8章まで確実に抜け漏れなく完走
- 【全8章完全性自動監査】生成後に全章(TAB_1〜8)の存在を厳格検証し、欠落時の不正上書きを100%防止
- 【タイムアウト75秒最適化】混雑時の通信揺らぎを安全に吸収しつつフリーズを抑止
- 【Geminiモデル厳格固定＆自動フォールバック】主軸(gemini-3.5-flash-lite) ＆ 控(gemini-flash-lite-latest)
- 【親切エラーハンドリング】HTTPステータスコードやタイムアウトに応じた次の具体的行動を日本語で案内
- 【JSオブジェクト型履歴パース】version.js 等の VersionManager = { history: [...] } を直接検出・吸い上げ
- 【親切な品質判定】コード担保済みだが実機環境確認が必要な動的項目に対し、理由と実装関数を明記して「🟡 要確認」と判定
- 【厳格な品質判定基準の統一】判定語彙を「🟢 適合」「🟡 要確認」「🔴 不適合」の3段階に完全固定
- 【全プロダクト統一版数外出し】バージョン情報・履歴を spec_version.json と完全自動連携
- 【マインド採掘エンジン（Mind Miner）】コード内のガイド文章やコメントから開発者の魂・哲学を自律抽出
- 【真のプロダクト名検知】HTMLの<title>やコメントから真のシステム名を特定
- 【重要ドメイン関数の優先抽出】コアロジックを担う重要関数を優先解析
- 【完全住み分け除外設計】他プロジェクト解析時も自己評価時も、spec_version.json はコード一覧に入らず裏方に徹底
"""

import hashlib
import html
import http.server
import json
import os
import re
import socket
import socketserver
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

DEFAULT_PORT = 8765
BASE_DIR = Path(__file__).resolve().parent
FALLBACK_PROJECT_NAME = BASE_DIR.name
DRAFT_FILE = BASE_DIR / "spec_studio_draft.json"
SNAPSHOT_FILE = BASE_DIR / "spec_studio_snapshot.json"
VERSION_FILE = BASE_DIR / "spec_version.json"

# ==============================================================================
# Gemini API モデル固定定義 ＆ タイムアウト設計
# ==============================================================================
PRIMARY_MODEL = "gemini-3.5-flash-lite"        # 第1優先（主軸・最速）
BACKUP_MODEL = "gemini-flash-lite-latest"     # 第2優先（バックアップ・高可用性）
CONNECT_TEST_TIMEOUT = 10                     # 疎通テスト用タイムアウト（秒）
GENERATE_TIMEOUT = 75                         # 生成処理用タイムアウト（秒：突発的な混雑遅延を安全に吸収）

# ==============================================================================
# 0. バージョン外出し連携マネージャー（完全同期 ＆ フェイルセーフ）
# ==============================================================================
def load_spec_version_data() -> dict:
    """spec_version.json からツールのバージョン情報・更新履歴を動的読み込み"""
    default_version_data = {
        "current_version": "1.0.0",
        "updated_date": datetime.now().strftime("%Y-%m-%d"),
        "update_type": "● 正式リリース",
        "release_notes": [
            "【正式リリース】現場設計書ダッシュボード自動作成システム SpecStudio Ver 1.0.0 正式版策定",
            "【3フェーズ分割生成】MAX_TOKENS上限を根本回避し、第8章まで抜け漏れなく完全執筆する安全設計を確立",
            "【全8章完全性監査】全章(TAB_1〜8)の出力が完全であることを検証し、不完全なHTMLの上書き保存を100%防止",
            "【Gemini API固定＆2段階フォールバック】gemini-3.5-flash-lite を主軸とし gemini-flash-lite-latest を控える二重冗長化",
            "【タイムアウト75秒最適化】ピーク時の通信揺らぎを安全に吸収し、接続エラーと打ち切りを同時に防止",
            "【親切エラーハンドリング】混雑時や利用制限時の具体的リカバリー手順を日本語で案内",
            "【版数管理の完全外出し】全プロダクト標準基準に準拠し、バージョン情報・履歴を spec_version.json へ完全分離",
            "【JSオブジェクト型履歴パース】version.js等のVersionManager構文から直接更新履歴を抽出",
            "【客観的品質判定の完全統一】判定ステータスを「適合・要確認・不適合」の3段階に完全固定し基準を明文化",
            "【親切な実機確認ガイド】コード上担保済みである旨と実機検証が必要な理由を第6章に明記",
            "【マインド採掘エンジン】コード内のガイド文章やコメントから開発者の魂・哲学を自律抽出",
            "【真のプロダクト名検知】HTMLタイトルやコメントから真のシステム名を特定"
        ],
        "history": [
            {
                "version": "1.0.0",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "type": "● 正式リリース",
                "summary": "SpecStudio 正式版リリース。3フェーズ分割生成、全8章完全性監査、Gemini二重冗長フォールバック、版数JSON外出し、客観品質判定"
            }
        ]
    }

    if VERSION_FILE.exists():
        try:
            data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "current_version" in data:
                return data
        except Exception as e:
            print(f"spec_version.json 読み込み警告: {e}")

    return default_version_data

SYSTEM_META = load_spec_version_data()
__version__ = SYSTEM_META.get("current_version", "1.0.0")

# ==============================================================================
# 1. ソースコード ＆ メディアアセットの静的スキャナー（マインド採掘対応）
# ==============================================================================
def calculate_file_hash(content: str) -> str:
    """ファイルの物理的変更を検知するためのMD5ハッシュ計算"""
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def detect_project_title_from_code(sorted_files) -> str:
    """フォルダ名に惑わされず、HTMLの<title>やコメントから真のシステム名を検出"""
    for file_path in sorted_files:
        if file_path.suffix.lower() == ".html":
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")[:4000]
                m_title = re.search(r'<title>(.*?)(?:\||-|—|\n|</title>)', text, re.IGNORECASE)
                if m_title:
                    raw_title = m_title.group(1).strip()
                    clean_title = re.sub(r'^[^\w\s\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+', '', raw_title).strip()
                    if clean_title and len(clean_title) >= 2:
                        return clean_title
                m_cmt = re.search(r'【\s*(.+?)\s*(?:バージョン情報|Ver|Version|コックピット|システム)\s*】', text)
                if m_cmt:
                    return m_cmt.group(1).strip()
            except Exception:
                continue

    for file_path in sorted_files:
        name_lower = file_path.name.lower()
        if name_lower == "package.json":
            try:
                pj = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(pj, dict) and "name" in pj and pj["name"]:
                    return str(pj["name"]).strip()
            except Exception:
                pass

    return FALLBACK_PROJECT_NAME

def detect_version_from_project(sorted_files, prev_snapshot_version=None) -> str:
    """多層フォールバックによる確定的バージョン検出（version.js等のJSオブジェクト構文も最優先解析）"""
    for file_path in sorted_files:
        if "version" in file_path.name.lower() or file_path.suffix.lower() in {".js", ".ts"}:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                m_vm = re.search(r'(?:current|version)\s*:\s*[\'"]v?([0-9]+(?:\.[0-9]+)+[a-zA-Z0-9_\-]*)[\'"]', text, re.IGNORECASE)
                if m_vm:
                    return m_vm.group(1).strip()
            except Exception:
                pass

    for file_path in sorted_files:
        name_lower = file_path.name.lower()
        if name_lower == "package.json":
            try:
                pj = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(pj, dict) and "version" in pj and pj["version"]:
                    return str(pj["version"]).strip().lstrip("vV")
            except Exception as e:
                print(f"package.json パース注意: {e}")
        elif name_lower in ("pyproject.toml", "setup.cfg"):
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'version\s*=\s*[\'"]v?([0-9a-zA-Z\.\-]+)[\'"]', text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            except Exception as e:
                print(f"設定ファイル読み込み注意: {e}")

    for file_path in sorted_files:
        if file_path.suffix.lower() in {".html", ".js", ".ts", ".py"}:
            try:
                head_text = file_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                m = re.search(r'(?:バージョン|Version|Ver|Rev)\s*[:：=]\s*V?([0-9]+(?:\.[0-9]+)+[a-zA-Z0-9_\-]*)', head_text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            except Exception:
                continue

    for file_path in sorted_files:
        if file_path.suffix.lower() in {".py", ".js", ".ts", ".html"}:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                m_py = re.search(r'__version__\s*=\s*[\'"]v?([0-9a-zA-Z\.\-]+)[\'"]', text, re.IGNORECASE)
                if m_py:
                    return m_py.group(1).strip()
                
                m_js = re.search(r'(?:const|let|var)?\s*(?:[a-zA-Z0-9_]*VERSION|[a-zA-Z0-9_]*version)\s*[:=]\s*[\'"]v?([0-9a-zA-Z\.\-]+)[\'"]', text)
                if m_js:
                    return m_js.group(1).strip()
            except Exception:
                continue

    if prev_snapshot_version:
        return str(prev_snapshot_version).lstrip("vV")

    return "1.0.0"

def extract_mind_and_philosophy(content: str, is_studio_self: bool = False) -> list[str]:
    """
    【マインド採掘（Mind Miner）】
    ソースコード内から開発者が込めた「哲学」「目的」「思想」「Why」にまつわる文章をあぶり出す。
    """
    mind_snippets = []
    
    if is_studio_self:
        mind_snippets.append("初心者と生成AIを繋ぐ『通訳コンパス』であり、コードに宿る開発者の魂・マインドをあぶり出して客観的な完全設計書と操作手順を自律生成するスタジオ。")
        mind_snippets.append("生成AI開発特有の全体像喪失、モグラ叩きバグ、デグレを防ぎ、プログラムの現在地と未来の青写真を誰の目にもクリアにする司令塔。")
        return mind_snippets

    guide_match = re.search(r'(?:本システムの目的|哲学 ＆ 設計思想|ツールの志|思想背景|発想の原点|コンセプト|永久不変仕様書)([\s\S]*?)(?=(?:<\/div>|<\/p>|\n\s*\n\s*[A-Z#=]|$))', content)
    if guide_match:
        clean_snip = re.sub(r'<[^>]+>', ' ', guide_match.group(0))
        clean_snip = re.sub(r'\s+', ' ', clean_snip).strip()
        if len(clean_snip) > 20:
            mind_snippets.append(clean_snip[:280])

    cmt_match = re.search(r'(?:システム思想|思想を|発想の原点|思考背景Why)([\s\S]*?)(?=(?:【|\n\s*\n|\*\/|-->|$))', content)
    if cmt_match:
        clean_cmt = re.sub(r'\s+', ' ', cmt_match.group(0)).strip()
        if len(clean_cmt) > 15:
            mind_snippets.append(clean_cmt[:240])

    return mind_snippets

def extract_changelog_from_code(content: str) -> dict:
    """
    【高精度改修履歴抽出エンジン】
    1. コメントブロック内の記述
    2. version.js 等の JavaScript オブジェクト構文（history: [ { version, date, changes } ]）
    の両方を検出し、生きた更新履歴を100%吸い上げる。
    """
    items = []
    history_records = []
    version_title = ""

    js_hist_match = re.search(r'history\s*:\s*\[([\s\S]*?)\]', content)
    if js_hist_match:
        raw_entries = js_hist_match.group(1)
        obj_matches = re.finditer(r'\{([^{}]+)\}', raw_entries)
        for om in obj_matches:
            block = om.group(1)
            v_m = re.search(r'version\s*:\s*[\'"]([^\'"]+)[\'"]', block)
            d_m = re.search(r'date\s*:\s*[\'"]([^\'"]+)[\'"]', block)
            c_m = re.search(r'(?:changes|summary|desc)\s*:\s*[\'"]([^\'"]+)[\'"]', block)
            if v_m:
                v_str = v_m.group(1)
                d_str = d_m.group(1) if d_m else ""
                c_str = c_m.group(1) if c_m else ""
                history_records.append({
                    "version": v_str.lstrip("vV"),
                    "date": d_str,
                    "summary": c_str
                })
        if history_records:
            latest = history_records[0]
            version_title = f"Ver {latest['version']}"
            if latest.get("summary"):
                split_items = [s.strip() for s in re.split(r'[、；;\n]', latest["summary"]) if s.strip()]
                items.extend(split_items[:8])

    if not history_records:
        comment_blocks = []
        for m in re.finditer(r'<!--([\s\S]*?)-->', content):
            comment_blocks.append(m.group(1))
        for m in re.finditer(r'/\*([\s\S]*?)\*/', content):
            comment_blocks.append(m.group(1))
        for m in re.finditer(r'^(?:#![^\n]+\n)?(?:\s*#.*?coding[^\n]+\n)?\s*[\'"]{3}([\s\S]*?)[\'"]{3}', content):
            comment_blocks.append(m.group(1))

        if comment_blocks:
            target_block = comment_blocks[0]
            v_match = re.search(r'(?:バージョン|Version|Ver|Rev)\s*[:：=]?\s*([^\n\r]+)', target_block, re.IGNORECASE)
            if v_match:
                version_title = v_match.group(1).strip()

            content_section = target_block
            sec_match = re.search(r'(?:更新内容|改修内容|変更点|Changelog)\s*[:：]([\s\S]*?)(?=(?:【|===|---|\n\s*\n\s*[A-Zあ-ん]|$))', target_block, re.IGNORECASE)
            if sec_match:
                content_section = sec_match.group(1)

            for line in content_section.splitlines():
                line_s = line.strip()
                m_item = re.match(r'^(?:(?:\d+[\.\)]|[-\*・•])\s*|【)(.+)', line_s)
                if m_item:
                    item_text = line_s
                    item_text = re.sub(r'^(?:\d+[\.\)]|[-\*・•])\s*', '', item_text).strip()
                    if item_text and not item_text.startswith(('バージョン', 'Version', 'Ver', 'http')):
                        items.append(item_text)

            hist_sec = re.search(r'(?:バージョン更新履歴|更新履歴|Release Notes)\s*[:：]?\s*(?:（[^）]+）)?([\s\S]*?)(?=(?:===|---|\*/|-->|$))', target_block, re.IGNORECASE)
            if hist_sec:
                for line in hist_sec.group(1).splitlines():
                    line_s = line.strip()
                    m_rec = re.search(r'V?([0-9]+(?:\.[0-9]+)+)\s*(?:\(([^)]+)\))?\s*[:：]\s*(.+)', line_s)
                    if m_rec:
                        history_records.append({
                            "version": m_rec.group(1),
                            "date": m_rec.group(2) or "",
                            "summary": m_rec.group(3).strip()
                        })

    has_changelog = bool(version_title or items or history_records)
    return {
        "has_changelog": has_changelog,
        "version_title": version_title,
        "items": items[:8],
        "history_records": history_records
    }

def detect_api_signals(content: str, is_studio_self: bool = False) -> dict:
    """外部連携シグナルを検知し、重要度別に格付け分類"""
    core_apis = []
    browser_apis = []
    cdn_assets = []

    if is_studio_self:
        if "generativelanguage.googleapis.com" in content:
            core_apis.append(f"Google Gemini API（AI推論・{PRIMARY_MODEL} / {BACKUP_MODEL}）")
        return {
            "core": list(dict.fromkeys(core_apis)),
            "browser": [],
            "cdn": []
        }

    # 1. Google系中核API
    if re.search(r'googleapis\.com/calendar|gapi\.client\.calendar|calendar\.events', content, re.IGNORECASE):
        core_apis.append("Google Calendar API（カレンダー予定連携）")
    if re.search(r'accounts\.google\.com|google\.accounts\.id|gapi\.auth2|oauth2', content, re.IGNORECASE):
        core_apis.append("Google Identity / OAuth 2.0（認証セッション）")
    if re.search(r'googleapis\.com/drive|gapi\.client\.drive', content, re.IGNORECASE):
        core_apis.append("Google Drive API（ストレージ連携）")
    if re.search(r'googleapis\.com/sheets|gapi\.client\.sheets', content, re.IGNORECASE):
        core_apis.append("Google Sheets API（スプレッドシート連携）")

    # 2. AI・LLM系中核API
    if re.search(r'generativelanguage\.googleapis\.com|google\.generativeai|gemini', content, re.IGNORECASE):
        core_apis.append(f"Google Gemini API（AI推論・{PRIMARY_MODEL} / {BACKUP_MODEL}）")
    if re.search(r'api\.openai\.com', content, re.IGNORECASE):
        core_apis.append("OpenAI API（ChatGPT/LLM連携）")
    if re.search(r'api\.anthropic\.com', content, re.IGNORECASE):
        core_apis.append("Anthropic Claude API（LLM対話連携）")
    if re.search(r'localhost:50021|api\.tts\.quest', content, re.IGNORECASE):
        core_apis.append("VOICEVOX API（高品質音声合成エンジン）")

    # 3. ブラウザ標準API
    if re.search(r'speechSynthesis|SpeechSynthesisUtterance', content):
        browser_apis.append("Web Speech API（ブラウザ標準音声合成）")
    if re.search(r'webkitSpeechRecognition|SpeechRecognition', content):
        browser_apis.append("Web Speech API（ブラウザ標準音声認識）")

    # 4. 静的CDN・フォント
    if re.search(r'cdn\.tailwindcss\.com', content):
        cdn_assets.append("Tailwind CSS CDN（画面スタイリング配信）")
    if re.search(r'unpkg\.com/lucide', content):
        cdn_assets.append("Lucide Icons CDN（UIアイコン配信）")
    if re.search(r'fonts\.googleapis\.com|fonts\.gstatic\.com', content):
        cdn_assets.append("Google Fonts CDN（Webフォント配信）")

    return {
        "core": list(dict.fromkeys(core_apis)),
        "browser": list(dict.fromkeys(browser_apis)),
        "cdn": list(dict.fromkeys(cdn_assets))
    }

def scan_project_files():
    """プログラムファイル、起動バッチ、およびメディアアセットを収集・解析"""
    code_exts = {".js", ".html", ".css", ".py", ".json", ".ts", ".jsx", ".tsx", ".sql", ".sh", ".bat", ".cmd"}
    img_exts = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico"}
    audio_exts = {".mp3", ".wav", ".ogg", ".m4a"}

    ignore_files = {
        "system_spec_dashboard.html", "spec_studio_draft.json", "spec_studio_snapshot.json",
        "spec_version.json", ".env", ".gitignore", "package-lock.json", "yarn.lock"
    }

    all_entries = sorted([p for p in BASE_DIR.iterdir() if p.is_file()], key=lambda x: x.name.lower())

    studio_self_code_files = {"spec_studio.py", "start_spec_studio.bat", "start_spec_studio.cmd"}
    other_code_files = [
        p for p in all_entries 
        if p.name not in studio_self_code_files 
        and p.name not in ignore_files 
        and not p.name.startswith(("system_spec_dashboard_", ".git"))
        and p.suffix.lower() in code_exts
    ]

    is_self_eval = False
    if other_code_files:
        ignore_files.update(studio_self_code_files)
    else:
        is_self_eval = True

    files_data = []
    image_assets = []
    audio_assets = []
    launch_batches = []
    total_lines = 0

    all_core_apis = []
    all_browser_apis = []
    all_cdn_assets = []
    project_changelogs = []
    all_mind_snippets = []

    valid_entries = [p for p in all_entries if p.name not in ignore_files and not p.name.startswith(("system_spec_dashboard_", ".git"))]
    all_file_names = {f.name for f in valid_entries}

    prev_ver = None
    if SNAPSHOT_FILE.exists():
        try:
            prev_ver = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8")).get("version")
        except Exception as e:
            print(f"スナップショット読み込み警告: {e}")

    if is_self_eval:
        detected_version = __version__
        detected_title = "SpecStudio（現場設計書ダッシュボード自動作成システム）"
    else:
        detected_version = detect_version_from_project(valid_entries, prev_ver)
        detected_title = detect_project_title_from_code(valid_entries)

    for file_path in valid_entries:
        fname = file_path.name
        if any(sec in fname.lower() for sec in ["secret", "token", "credential", "private_key"]):
            continue

        ext = file_path.suffix.lower()

        if ext in img_exts:
            size_kb = round(file_path.stat().st_size / 1024, 1)
            image_assets.append({"name": fname, "size_kb": size_kb})
            continue

        if ext in audio_exts:
            size_kb = round(file_path.stat().st_size / 1024, 1)
            audio_assets.append({"name": fname, "size_kb": size_kb})
            continue

        if ext in {".bat", ".cmd"}:
            launch_batches.append(fname)

        if ext in code_exts:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"ファイル読み込みエラー ({fname}): {e}")
                continue

            lines = content.splitlines()
            line_count = len(lines)
            total_lines += line_count
            file_hash = calculate_file_hash(content)

            minds = extract_mind_and_philosophy(content, is_studio_self=(is_self_eval and fname == "spec_studio.py"))
            all_mind_snippets.extend(minds)

            code_cl = extract_changelog_from_code(content)
            if code_cl["has_changelog"]:
                project_changelogs.append({"file": fname, "data": code_cl})

            api_dict = detect_api_signals(content, is_studio_self=(is_self_eval and fname == "spec_studio.py"))
            for a in api_dict["core"]:
                if a not in all_core_apis: all_core_apis.append(a)
            for a in api_dict["browser"]:
                if a not in all_browser_apis: all_browser_apis.append(a)
            for a in api_dict["cdn"]:
                if a not in all_cdn_assets: all_cdn_assets.append(a)

            elements = []
            priority_elements = []
            references = []

            for other_name in all_file_names:
                if other_name != fname and other_name in content:
                    references.append(other_name)

            for line in lines:
                cls_match = re.search(r"^\s*class\s+([a-zA-Z0-9_]+)", line)
                fn_match = re.search(r"^\s*def\s+([a-zA-Z0-9_]+)", line)
                js_fn_match = re.search(r"function\s+([a-zA-Z0-9_]+)", line)
                const_fn = re.search(r"(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:function|\()", line)

                elem_name = ""
                if cls_match: elem_name = f"class {cls_match.group(1)}"
                elif fn_match: elem_name = f"{fn_match.group(1)}()"
                elif js_fn_match: elem_name = f"{js_fn_match.group(1)}()"
                elif const_fn: elem_name = f"{const_fn.group(1)}()"

                if elem_name:
                    low_name = elem_name.lower()
                    if any(k in low_name for k in ["advice", "comment", "step", "action", "wish", "import", "spotlight", "task", "flow", "mind", "why", "sync"]):
                        priority_elements.append(elem_name)
                    else:
                        elements.append(elem_name)

            sorted_elements = list(dict.fromkeys(priority_elements + elements))

            files_data.append({
                "name": fname,
                "ext": ext,
                "lines": line_count,
                "hash": file_hash,
                "elements": sorted_elements[:22],
                "references": references,
                "core_apis": api_dict["core"],
                "browser_apis": api_dict["browser"],
                "cdn_assets": api_dict["cdn"]
            })

    has_changelog = len(project_changelogs) > 0
    if is_self_eval and VERSION_FILE.exists():
        has_changelog = True

    files_data.sort(key=lambda x: x["lines"], reverse=True)
    return {
        "project_name": detected_title,
        "version": detected_version,
        "is_self_eval": is_self_eval,
        "files": files_data,
        "image_assets": image_assets,
        "audio_assets": audio_assets,
        "launch_batches": launch_batches,
        "total_files": len(files_data),
        "total_lines": total_lines,
        "core_apis": all_core_apis,
        "browser_apis": all_browser_apis,
        "cdn_assets": all_cdn_assets,
        "external_apis": all_core_apis + all_browser_apis,
        "project_changelogs": project_changelogs,
        "has_code_changelog": has_changelog,
        "mind_snippets": list(dict.fromkeys(all_mind_snippets))
    }

# ==============================================================================
# 2. コード内履歴抽出 ＆ バージョン飛び合算・差分ドッキングエンジン
# ==============================================================================
def sanitize_history_record(rec: dict) -> dict:
    """過去のJSONに保存されてしまったURLゴミや使い回し文言を完全クリーニングするフィルター"""
    rec_copy = dict(rec)
    rev = rec_copy.get("rev", 1)
    purpose = rec_copy.get("purpose", "")
    improvements = rec_copy.get("improvements", "")
    summary = rec_copy.get("summary", "")
    added = rec_copy.get("added_files", [])
    modified = rec_copy.get("modified_files", [])

    if "このゲームのコンセプトは" in purpose or "コンセプトは、生成AIでプログラム" in purpose:
        if added:
            purpose = f"新規モジュールの追加（{', '.join(added)}）"
            improvements = "機能拡張および責務分離の実現"
        elif modified:
            purpose = f"既存機能の改修・内部ロジック強化（{', '.join([str(m).split(' ')[0] for m in modified])}）"
            improvements = "内部ロジックの改善、エラー耐性の強化および動作安定化"
        else:
            purpose = "コードベースの調律および最適化"
            improvements = "動作の安定性向上"

    if not purpose or purpose.strip() == "":
        if rev == 1 or added:
            purpose = "初回ベースライン設計書・品質ダッシュボードの策定"
            improvements = "新規プロジェクトとしてのファイル体系、責務構造、運用ガイドラインの初版策定"
        elif modified:
            purpose = f"プログラム機能の改修・リファクタリング（{', '.join([str(m).split(' ')[0] for m in modified])}）"
            improvements = "内部ロジックの改善および安定稼働の確保"

    if not summary or summary.strip() == "" or "このゲームのコンセプト" in summary:
        if added:
            summary = f"【新設】{', '.join(added)}"
        elif modified:
            summary = f"【更新】{', '.join([str(m).split(' ')[0] for m in modified])}"
        else:
            summary = f"Rev.{rev} コード微調整"

    noise_patterns = [
        r'、?\s*外部エンドポイント:\s*https?://[^\s、\)]+',
        r'外部エンドポイント:\s*https?://[^\s、\)]+、?',
        r'、?\s*外部エンドポイント:[^\s、\)]+',
        r'外部エンドポイント:[^\s、\)]+、?',
        r'、?\s*Web Speech API（[^）]*）',
        r'Web Speech API（[^）]*）[、＆]?',
        r'、?\s*Web Speech API',
        r'Web Speech API[、＆]?'
    ]

    for pat in noise_patterns:
        purpose = re.sub(pat, '', purpose)
        improvements = re.sub(pat, '', improvements)
        summary = re.sub(pat, '', summary)

    clean_replacements = [
        (r'（[、\s]+', '（'),
        (r'[、\s]+）', '）'),
        (r'（\s*）', ''),
        (r'、+', '、'),
        (r'＆\s*＆', '＆'),
        (r'^\s*[、＆]\s*', ''),
        (r'\s*[、＆]\s*$', '')
    ]
    for pat, rep in clean_replacements:
        purpose = re.sub(pat, rep, purpose)
        improvements = re.sub(pat, rep, improvements)
        summary = re.sub(pat, rep, summary)

    rec_copy["purpose"] = purpose.strip()
    rec_copy["improvements"] = improvements.strip()
    rec_copy["summary"] = summary.strip()
    return rec_copy

def detect_semantic_feature_from_elements(new_elements: list[str]) -> str:
    """新設された関数名・キーワードから具体的な機能追加名称を推論（差分逆算用）"""
    elems_str = " ".join(new_elements).lower()

    if any(k in elems_str for k in ["comment", "advice", "step", "wish", "action"]):
        return "思考背景(Why)とツッコミ対話によるAI共創アクション支援機能"
    if any(k in elems_str for k in ["theme", "color", "dark", "palette", "settheme", "inittheme"]):
        return "画面テーマ・配色切替機能（UI拡張）"
    if any(k in elems_str for k in ["calendar", "event", "schedule"]):
        return "カレンダー同期連携機能"
    if any(k in elems_str for k in ["modal", "dialog", "popup"]):
        return "操作UI・ダイアログ拡張"
    if any(k in elems_str for k in ["export", "download", "save", "persist", "backup"]):
        return "データ永続化・セーフガード強化"
    if any(k in elems_str for k in ["speech", "voice", "record", "audio"]):
        return "音声入出力ハンドリング機能"
    if any(k in elems_str for k in ["auth", "login", "oauth", "token"]):
        return "認証セッション制御機構"
    if any(k in elems_str for k in ["filter", "search", "sort"]):
        return "検索・フィルタリングUI強化"

    return ""

def summarize_changelog_items(items: list[str]) -> str:
    """複数の更新項目から代表的な見出しキーワードを抽出し、ブツ切れを防いだスマートな要約行を生成"""
    if not items:
        return ""
    
    extracted_tags = []
    for it in items:
        m_tag = re.search(r'【([^】]+)】', it)
        if m_tag:
            tag_text = m_tag.group(1).split("・")[0].split("（")[0].strip()
            if tag_text:
                extracted_tags.append(tag_text[:14])
        else:
            clean_it = re.sub(r'^(?:(?:\d+[\.\)]|[-\*・•])\s*)', '', it).strip()
            clean_it = clean_it.split("：")[0].split("。")[0].split("（")[0].strip()
            if clean_it:
                extracted_tags.append(clean_it[:14])
    
    if extracted_tags:
        unique_tags = list(dict.fromkeys(extracted_tags))
        if len(unique_tags) > 2:
            return f"【{'・'.join(unique_tags[:2])} 等】"
        else:
            return f"【{'・'.join(unique_tags)}】"
    return f"【{items[0][:20]}】"

def inspect_code_diff(current_scan, concept="", traps=""):
    """
    【物理スナップショット起点 ＆ コード内・外部版数履歴ドッキングエンジン】
    - version.js や spec_version.json の履歴を最優先でドッキング
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    code_cls = current_scan.get("project_changelogs", [])
    primary_code_cl = code_cls[0]["data"] if code_cls else None

    external_release_notes = []
    if current_scan.get("is_self_eval") and VERSION_FILE.exists():
        try:
            v_data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
            external_release_notes = v_data.get("release_notes", [])
        except Exception:
            pass

    if not SNAPSHOT_FILE.exists():
        api_text = f"（中核連携: {', '.join(current_scan['core_apis'])}) " if current_scan['core_apis'] else "（内部完結型）"
        first_summary = f"初回ベースライン設計書・品質ダッシュボード確立 (Ver {current_scan['version']})"
        first_purpose = f"「{current_scan['project_name']}」の全体構造可視化および初期設計ベースラインの確立 {api_text}"
        first_improvements = "新規プロジェクトとしてのファイル体系、責務構造、運用ガイドラインの初版策定"

        if external_release_notes:
            first_improvements = "； ".join(external_release_notes[:4])
        elif primary_code_cl and primary_code_cl.get("items"):
            first_improvements = "、".join(primary_code_cl["items"][:3])

        return {
            "has_prev": False,
            "is_changed": True,
            "rev": 1,
            "history": [{
                "rev": 1,
                "version": current_scan["version"],
                "date": now_str,
                "summary": first_summary,
                "purpose": first_purpose,
                "improvements": first_improvements,
                "added_files": [f["name"] for f in current_scan["files"]],
                "modified_files": [],
                "removed_files": [],
                "net_lines": f"+{current_scan['total_lines']}"
            }],
            "created_at": now_str,
            "diff_summary": f"Rev.1 初回ベースライン確立 (Ver {current_scan['version']})"
        }

    prev_snap = {}
    try:
        loaded = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and "files" in loaded:
            prev_snap = loaded
    except Exception as e:
        print(f"スナップショットパース例外: {e}")

    prev_files = {f["name"]: f for f in prev_snap.get("files", []) if isinstance(f, dict) and "name" in f}
    prev_version = prev_snap.get("version", "1.0.0")

    has_prev_api_record = "core_apis" in prev_snap
    prev_core_apis = prev_snap.get("core_apis", [])
    current_files = {f["name"]: f for f in current_scan["files"]}
    current_core_apis = current_scan["core_apis"]

    new_core_apis = [a for a in current_core_apis if a not in prev_core_apis] if has_prev_api_record else []

    added_files = []
    removed_files = []
    modified_files = []
    net_lines_count = 0
    all_new_elements = []

    for name, c_data in current_files.items():
        if name not in prev_files:
            added_files.append({"name": name, "lines": c_data["lines"]})
            net_lines_count += c_data["lines"]
        else:
            p_data = prev_files[name]
            if c_data["hash"] != p_data.get("hash"):
                diff = c_data["lines"] - p_data.get("lines", 0)
                net_lines_count += diff
                new_elems = [e for e in c_data["elements"] if e not in p_data.get("elements", [])]
                all_new_elements.extend(new_elems)
                modified_files.append({
                    "name": name,
                    "diff": diff,
                    "new_elements": new_elems[:5]
                })

    for name in prev_files:
        if name not in current_files:
            removed_files.append(name)
            net_lines_count -= prev_files[name].get("lines", 0)

    is_changed = bool(added_files or removed_files or modified_files)
    prev_rev = prev_snap.get("rev", 1)
    new_rev = prev_rev + 1 if is_changed else prev_rev

    semantic_feature = detect_semantic_feature_from_elements(all_new_elements)

    diff_summary_parts = []
    if added_files:
        diff_summary_parts.append(f"【新設】{', '.join([f['name'] for f in added_files])}")
    if modified_files:
        diff_summary_parts.append(f"【更新】{', '.join([f['name'] for f in modified_files])}")
    if removed_files:
        diff_summary_parts.append(f"【削除】{', '.join(removed_files)}")

    raw_history = prev_snap.get("history", [])
    history = [sanitize_history_record(rec) for rec in raw_history]

    if is_changed:
        sign = "+" if net_lines_count >= 0 else ""

        code_intent = ""
        code_items = []
        is_version_jumped = False
        skipped_versions = []

        if external_release_notes:
            code_intent = f"Ver {current_scan['version']} 仕様拡充 ＆ 全プロダクト統一版数管理"
            code_items.extend(external_release_notes)
        elif primary_code_cl:
            if primary_code_cl.get("version_title"):
                code_intent = primary_code_cl["version_title"]
            if primary_code_cl.get("items"):
                code_items.extend(primary_code_cl["items"])

            hist_records = primary_code_cl.get("history_records", [])
            if hist_records and prev_version != current_scan["version"]:
                for rec in hist_records:
                    rec_v = rec.get("version", "").lstrip("vV")
                    if rec_v == current_scan["version"].lstrip("vV"):
                        continue
                    if rec_v == prev_version.lstrip("vV"):
                        break
                    skipped_versions.append(rec)

                if skipped_versions:
                    is_version_jumped = True

        compact_summary = summarize_changelog_items(code_items)

        purpose_parts = []
        improvement_parts = []

        if is_version_jumped:
            skipped_names = ", ".join([f"V.{s['version']}" for s in skipped_versions])
            purpose_parts.append(f"Ver {current_scan['version']} への段階的改修の反映（※前回測定 Ver {prev_version} から {skipped_names} を合算集約）")
            for s in skipped_versions:
                improvement_parts.append(f"[V.{s['version']}] {s['summary']}")
            if code_items:
                improvement_parts.extend(code_items)
        elif code_intent:
            source_label = "（外部版数管理 spec_version.json より抽出）" if external_release_notes else "（プログラム版数定義より抽出）"
            purpose_parts.append(f"{code_intent} {source_label}")
            if code_items:
                improvement_parts.extend(code_items)
            else:
                improvement_parts.append("記録された仕様改修の実装")
        elif new_core_apis:
            api_names = "、".join([a.split("（")[0] for a in new_core_apis])
            purpose_parts.append(f"外部クラウド・API連携機能の実装（{api_names}）")
            improvement_parts.append(f"{api_names} との双方向連携によるデータ同期と自動化の実現")
        elif semantic_feature:
            purpose_parts.append(f"{semantic_feature}の実装およびUI操作性の向上")
            improvement_parts.append(f"{semantic_feature}によるユーザビリティと操作体験の向上")

        if added_files and not code_intent:
            batch_adds = [f['name'] for f in added_files if f['name'].endswith(('.bat', '.cmd'))]
            code_adds = [f['name'] for f in added_files if not f['name'].endswith(('.bat', '.cmd'))]
            if batch_adds:
                purpose_parts.append(f"日常起動インターフェース整備（{', '.join(batch_adds)}）")
                improvement_parts.append("ワンクリック起動による運用性の向上")
            if code_adds:
                purpose_parts.append(f"新規プログラムモジュール新設（{', '.join(code_adds)}）")
                improvement_parts.append("機能拡張および責務分離")

        if modified_files and not purpose_parts:
            mod_names = [f['name'] for f in modified_files]
            purpose_parts.append(f"内部ロジックおよび機能の改善・リファクタリング（{', '.join(mod_names)}）")
            improvement_parts.append("コード最適化、処理効率およびエラー耐性の向上（※コード内に改修履歴なし）")

        cur_purpose = " ＆ ".join(purpose_parts) if purpose_parts else "コード微調整および安定化改修"
        cur_improvements = "； ".join(improvement_parts) if improvement_parts else "機能の安定稼働および品質向上"

        summary_title = "; ".join(diff_summary_parts) if diff_summary_parts else "コード微調整"
        if compact_summary:
            summary_title = f"{summary_title} {compact_summary}"
        elif code_intent:
            summary_title = f"{summary_title} [{code_intent[:24]}]"

        history.append({
            "rev": new_rev,
            "version": current_scan["version"],
            "date": now_str,
            "summary": summary_title,
            "purpose": cur_purpose,
            "improvements": cur_improvements,
            "added_files": [f["name"] for f in added_files],
            "modified_files": [f"{f['name']} ({'+' if f['diff']>=0 else ''}{f['diff']}行)" for f in modified_files],
            "removed_files": removed_files,
            "net_lines": f"{sign}{net_lines_count}"
        })

    latest_rev_record = history[-1] if history else {}
    latest_rev_summary = latest_rev_record.get("summary", "初回ベースライン確立")
    latest_rev_net = latest_rev_record.get("net_lines", "+0")

    return {
        "has_prev": True,
        "is_changed": is_changed,
        "prev_rev": prev_rev,
        "rev": new_rev,
        "history": history,
        "prev_date": prev_snap.get("created_at", "不明"),
        "created_at": now_str,
        "latest_rev_summary": latest_rev_summary,
        "latest_rev_net": latest_rev_net,
        "diff_summary": f"Rev.{new_rev} 改修実績: {latest_rev_summary} ({latest_rev_net}行)"
    }

def save_snapshot(current_scan, diff_info):
    """スナップショットJSONの永続化"""
    data = {
        "rev": diff_info["rev"],
        "project_name": current_scan["project_name"],
        "version": current_scan["version"],
        "created_at": diff_info["created_at"],
        "history": diff_info.get("history", []),
        "total_files": current_scan["total_files"],
        "total_lines": current_scan["total_lines"],
        "core_apis": current_scan["core_apis"],
        "browser_apis": current_scan["browser_apis"],
        "cdn_assets": current_scan["cdn_assets"],
        "external_apis": current_scan["external_apis"],
        "files": current_scan["files"]
    }
    try:
        SNAPSHOT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"スナップショット保存警告: {e}")

# ==============================================================================
# 3. Gemini API クライアント（固定モデル2段階フォールバック ＆ 親切エラー案内）
# ==============================================================================
def format_friendly_http_error(e: urllib.error.HTTPError, model_name: str) -> str:
    """HTTPステータスコードに応じた日本語の具体的アクションガイドを生成"""
    err_body = ""
    try:
        err_body = e.read().decode("utf-8", errors="ignore")
        err_json = json.loads(err_body)
        raw_msg = err_json.get("error", {}).get("message", "")
    except Exception:
        raw_msg = err_body[:180]

    code = e.code
    if code in (401, 403):
        return (
            f"【認証エラー ({code})】APIキーが無効、またはアクセス権限がありません。\n"
            f"👉 対処法：Google AI Studio ( https://aistudio.google.com/app/apikey ) で有効なAPIキーを再取得し、貼り直してください。"
        )
    elif code == 429:
        return (
            f"【利用上限・過負荷 ({code})】Gemini API の利用上限（レートリミット）に達しました。\n"
            f"👉 対処法：1〜2分ほど時間を置いてから再度ボタンを押してください。"
        )
    elif code == 404:
        return (
            f"【モデル不存在 ({code})】指定モデル '{model_name}' が見つかりませんでした。\n"
            f"👉 対処法：Google側でモデルが更新された可能性があります。システム管理者に連絡してください。"
        )
    elif code in (500, 502, 503, 504):
        return (
            f"【Google側サーバー混雑・過負荷 ({code})】GoogleのAIサービスが一時的に混雑またはメンテナンス中です。\n"
            f"👉 対処法：時間を少し（1〜3分程度）置いてから再度お試しください。"
        )
    elif code == 400:
        return (
            f"【リクエスト形式エラー (400)】プロンプトの構成またはトークン数が規定を超えた可能性があります。\n"
            f"詳細: {raw_msg if raw_msg else 'Invalid argument'}"
        )
    else:
        return f"【Google API 通信エラー ({code})】{raw_msg if raw_msg else '原因不明のエラーが発生しました。'}"

def test_gemini_connection(api_key: str) -> tuple[bool, str, str]:
    """
    固定2モデル（3.5-flash-lite ➔ flash-lite-latest）の接続テスト。
    10秒の短時間タイムアウトで迅速に判定。
    戻り値: (成功フラグ, 採用モデル名, メッセージ)
    """
    models_to_try = [PRIMARY_MODEL, BACKUP_MODEL]
    last_err_msg = ""

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 5}
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=CONNECT_TEST_TIMEOUT) as resp:
                if resp.status == 200:
                    return True, model_name, f"接続成功（稼働モデル: {model_name}）"
        except urllib.error.HTTPError as e:
            last_err_msg = format_friendly_http_error(e, model_name)
            if e.code in (401, 403):
                return False, "", last_err_msg
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            last_err_msg = "Google API への通信がタイムアウトしました。回線環境をご確認ください。"
        except Exception as e:
            last_err_msg = f"接続エラー: {str(e)}"

    return False, "", last_err_msg

def call_gemini_api(api_key: str, prompt: str, system_instruction: str = None) -> tuple[str, str]:
    """
    Gemini APIを安全に呼び出し、2段階自動フォールバックを実行する。
    - 第1優先: gemini-3.5-flash-lite (75秒タイムアウト)
    - エラー(429, 503, タイムアウト等)時は即座に第2優先: gemini-flash-lite-latest へフォールバック
    """
    models_to_try = [
        (PRIMARY_MODEL, "主軸モデル"),
        (BACKUP_MODEL, "高可用バックアップモデル")
    ]
    last_exception_msg = ""

    for idx, (model_name, role_label) in enumerate(models_to_try):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
        }
        if system_instruction:
            payload["systemInstruction"] = {"role": "system", "parts": [{"text": system_instruction}]}

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=GENERATE_TIMEOUT) as response:
                result = json.loads(response.read().decode("utf-8"))
                candidate = result["candidates"][0]
                finish_reason = candidate.get("finishReason", "")

                if finish_reason == "MAX_TOKENS":
                    print(f"【警告】生成トークン上限(8192)に達した可能性があります（モデル: {model_name}）。")

                text = candidate["content"]["parts"][0]["text"]
                return text, model_name

        except urllib.error.HTTPError as e:
            err_msg = format_friendly_http_error(e, model_name)
            last_exception_msg = err_msg
            print(f"[{role_label}: {model_name}] HTTPエラー ({e.code}): {err_msg.splitlines()[0]}")
            if e.code in (401, 403):
                raise RuntimeError(err_msg)
            if idx < len(models_to_try) - 1:
                print(f"👉 控えのバックアップモデル（{models_to_try[idx+1][0]}）へ自動フォールバックします...")
                time.sleep(1)
                continue

        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            timeout_msg = (
                f"【通信タイムアウト】Google API（{model_name}）からの応答が{GENERATE_TIMEOUT}秒以内に受信できませんでした。\n"
                f"👉 Googleサーバーが混雑しているか回線が不安定です。時間を置いてお試しください。"
            )
            last_exception_msg = timeout_msg
            print(f"[{role_label}: {model_name}] タイムアウト検知")
            if idx < len(models_to_try) - 1:
                print(f"👉 控えのバックアップモデル（{models_to_try[idx+1][0]}）へ自動フォールバックします...")
                time.sleep(1)
                continue

        except Exception as e:
            general_msg = f"【予期せぬ通信エラー】{str(e)}"
            last_exception_msg = general_msg
            print(f"[{role_label}: {model_name}] 例外検知: {e}")
            if idx < len(models_to_try) - 1:
                print(f"👉 控えのバックアップモデル（{models_to_try[idx+1][0]}）へ自動フォールバックします...")
                time.sleep(1)
                continue

    raise RuntimeError(last_exception_msg)

# ==============================================================================
# 4. リッチWebウィザード画面
# ==============================================================================
WIZARD_HTML = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpecStudio - 現場設計書ダッシュボード自動作成スタジオ</title>
<style>
  :root {{
    --bg-main: #0b0f19;
    --bg-card: rgba(22, 30, 49, 0.75);
    --border-color: rgba(255, 255, 255, 0.1);
    --border-focus: #6366f1;
    --primary: #4f46e5;
    --primary-hover: #4338ca;
    --accent: #06b6d4;
    --accent-emerald: #10b981;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
    --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0b0f19 75%);
    color: var(--text-main);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
    line-height: 1.6;
    padding-bottom: 80px;
    min-height: 100vh;
  }}
  header {{
    border-bottom: 1px solid var(--border-color);
    background: rgba(11, 15, 25, 0.8);
    backdrop-filter: blur(12px);
    position: sticky; top: 0; z-index: 50; padding: 16px 32px;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; }}
  .brand-logo {{
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, var(--accent), var(--primary));
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; box-shadow: 0 0 15px rgba(99, 102, 241, 0.5);
  }}
  .brand-text h1 {{
    font-size: 1.25rem; font-weight: 800; letter-spacing: -0.02em;
    background: linear-gradient(to right, #fff, #cbd5e1);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .brand-text p {{ font-size: 0.78rem; color: var(--text-muted); }}
  
  .header-actions {{ display: flex; align-items: center; gap: 12px; }}

  .btn-guide-modal {{
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.15), rgba(99, 102, 241, 0.2));
    border: 1px solid rgba(6, 182, 212, 0.4);
    color: #e0f2fe;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 800;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }}
  .btn-guide-modal:hover {{
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.3), rgba(99, 102, 241, 0.35));
    border-color: var(--accent);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25);
  }}

  .container {{ max-width: 1080px; margin: 36px auto; padding: 0 24px; display: flex; flex-direction: column; gap: 28px; }}
  .card {{
    background: var(--bg-card); border: 1px solid var(--border-color);
    border-radius: 18px; padding: 30px; backdrop-filter: blur(16px);
    box-shadow: var(--glass-shadow);
  }}
  .card-title {{ font-size: 1.35rem; font-weight: 800; margin-bottom: 6px; display: flex; align-items: center; gap: 10px; color: #fff; }}
  .card-subtitle {{ font-size: 0.9rem; color: var(--text-muted); margin-bottom: 22px; }}
  .guide-box {{
    background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 20px;
  }}
  .guide-steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 12px; }}
  .guide-step {{
    background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px; padding: 12px 14px; font-size: 0.85rem;
  }}
  .guide-step-num {{
    display: inline-block; background: var(--primary); color: #fff;
    width: 22px; height: 22px; border-radius: 50%; text-align: center;
    line-height: 22px; font-size: 0.75rem; font-weight: bold; margin-right: 6px;
  }}
  .input-group {{ display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }}
  label {{ font-size: 0.9rem; font-weight: 700; color: #e2e8f0; display: flex; justify-content: space-between; }}
  .sub-label {{ font-size: 0.8rem; color: var(--text-muted); font-weight: normal; }}
  input[type="text"], input[type="password"], textarea {{
    background: rgba(11, 15, 25, 0.8); border: 1px solid var(--border-color);
    border-radius: 10px; padding: 14px 16px; color: #fff; font-size: 0.95rem;
    font-family: inherit; transition: all 0.2s;
  }}
  input:focus, textarea:focus {{
    outline: none; border-color: var(--border-focus);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  }}
  textarea {{ min-height: 120px; resize: vertical; line-height: 1.6; }}

  .btn {{
    display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    padding: 12px 24px; border-radius: 10px; font-size: 0.95rem; font-weight: 700;
    cursor: pointer; border: none; transition: all 0.2s;
    white-space: nowrap;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, var(--primary), #6366f1); color: #fff;
    box-shadow: 0 4px 15px rgba(79, 70, 229, 0.4);
  }}
  .btn-primary:hover {{ background: linear-gradient(135deg, var(--primary-hover), var(--primary)); transform: translateY(-1px); }}
  .btn-secondary {{ background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border-color); color: #e2e8f0; }}
  .btn-secondary:hover {{ background: rgba(255, 255, 255, 0.14); }}

  .btn-generate-main {{
    padding: 18px 48px;
    font-size: 1.12rem;
    min-width: 580px;
    max-width: 100%;
    white-space: nowrap;
    letter-spacing: 0.02em;
  }}
  .btn-generate-main:disabled {{
    opacity: 0.6; cursor: not-allowed; transform: none !important;
  }}

  .quick-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; margin-bottom: 8px; }}
  .tag-btn {{
    background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-color);
    color: var(--accent); padding: 4px 10px; border-radius: 6px; font-size: 0.78rem;
    cursor: pointer; transition: all 0.2s;
  }}
  .tag-btn:hover {{ background: rgba(6, 182, 212, 0.15); border-color: var(--accent); }}
  .files-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-top: 12px; }}
  .file-chip {{
    background: rgba(11, 15, 25, 0.6); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 4px;
  }}
  .file-name {{ font-size: 0.88rem; font-weight: 700; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .file-meta {{ font-size: 0.78rem; color: var(--text-muted); display: flex; justify-content: space-between; }}
  .file-ref {{ font-size: 0.72rem; color: var(--accent); margin-top: 4px; word-break: break-all; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }}
  .badge-success {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }}
  .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }}
  .save-indicator {{ font-size: 0.78rem; color: var(--accent-emerald); display: none; align-items: center; gap: 4px; font-weight: 600; }}
  
  #loading-overlay {{
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(11, 15, 25, 0.94); backdrop-filter: blur(16px);
    z-index: 1000; display: none; flex-direction: column; align-items: center;
    justify-content: center; gap: 20px; text-align: center; padding: 20px;
  }}
  .spinner {{
    width: 60px; height: 60px; border: 4px solid rgba(99, 102, 241, 0.2);
    border-top: 4px solid var(--accent); border-radius: 50%;
    animation: spin 1s linear infinite;
  }}
  @keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}

  .progress-card {{
    background: rgba(22, 30, 49, 0.9); border: 1px solid rgba(99, 102, 241, 0.4);
    border-radius: 14px; padding: 20px 28px; max-width: 520px; width: 100%;
    text-align: left; box-shadow: var(--glass-shadow);
  }}
  .progress-step-item {{
    display: flex; align-items: center; gap: 10px; font-size: 0.9rem;
    color: var(--text-muted); margin-bottom: 8px; transition: all 0.3s;
  }}
  .progress-step-item.active {{ color: #fff; font-weight: bold; }}
  .progress-step-item.done {{ color: #34d399; }}

  #guide-modal-backdrop {{
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(11, 15, 25, 0.88); backdrop-filter: blur(16px);
    z-index: 2000; display: none; align-items: center; justify-content: center;
    padding: 24px; opacity: 0; transition: opacity 0.25s ease-out;
  }}
  #guide-modal-backdrop.show {{ display: flex; opacity: 1; }}
  .modal-window {{
    background: #121826; border: 1.5px solid rgba(99, 102, 241, 0.4);
    border-radius: 20px; max-width: 960px; width: 100%; max-height: 90vh;
    overflow-y: auto; box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8);
    display: flex; flex-direction: column; position: relative;
    transform: scale(0.96); transition: transform 0.25s ease-out;
  }}
  #guide-modal-backdrop.show .modal-window {{ transform: scale(1); }}
  
  .modal-header {{
    padding: 20px 28px; border-bottom: 1.5px solid rgba(255, 255, 255, 0.12);
    display: flex; justify-content: space-between; align-items: center;
    background: #121826; position: sticky; top: 0; z-index: 100;
  }}
  .modal-header h2 {{ font-size: 1.25rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 10px; }}
  .btn-modal-close {{
    background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border-color);
    color: var(--text-muted); width: 34px; height: 34px; border-radius: 8px;
    font-size: 1.2rem; cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
  }}
  .btn-modal-close:hover {{ background: rgba(255, 255, 255, 0.2); color: #fff; }}
  .modal-body {{ padding: 28px; display: flex; flex-direction: column; gap: 24px; font-size: 0.92rem; }}
  
  .modal-card {{ background: rgba(22, 30, 49, 0.7); border: 1px solid var(--border-color); border-radius: 14px; padding: 22px; }}
  .modal-card-title {{ font-size: 1.05rem; font-weight: 800; margin-bottom: 10px; color: #e2e8f0; display: flex; align-items: center; gap: 8px; }}
  
  .step-flow {{ display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }}
  .step-flow-item {{
    display: flex; align-items: flex-start; gap: 12px;
    background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border-color);
    border-radius: 10px; padding: 14px 16px; font-size: 0.88rem;
  }}
  .step-badge-num {{
    background: var(--primary); color: #fff; width: 24px; height: 24px;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 900; flex-shrink: 0; margin-top: 2px;
  }}
  .step-flow-content strong {{ color: #fff; display: block; margin-bottom: 2px; }}
  .step-flow-content span {{ color: var(--text-muted); font-size: 0.84rem; line-height: 1.5; }}

  .rule-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 10px; }}
  @media (max-width: 680px) {{ .rule-grid {{ grid-template-columns: 1fr; }} }}
  .rule-item {{ background: rgba(0, 0, 0, 0.35); border-left: 4px solid var(--accent); border-radius: 8px; padding: 14px; font-size: 0.88rem; }}
  .rule-item h4 {{ font-size: 0.95rem; font-weight: 800; color: #fff; margin-bottom: 4px; }}
  .rule-item p {{ color: var(--text-muted); line-height: 1.5; font-size: 0.82rem; }}

  .modal-alert-box {{
    background: rgba(245, 158, 11, 0.12); border: 1.5px solid rgba(245, 158, 11, 0.4);
    border-radius: 12px; padding: 16px 20px; color: #fde68a; font-size: 0.88rem;
  }}
  .modal-alert-box strong {{ color: #fbbf24; }}
  .modal-footer {{
    padding: 16px 28px; border-top: 1.5px solid rgba(255, 255, 255, 0.1);
    display: flex; justify-content: flex-end; background: #121826;
  }}
</style>
</head>
<body>

<header>
  <div class="brand">
    <div class="brand-logo">📐</div>
    <div class="brand-text">
      <h1>SpecStudio <span style="font-size: 0.8rem; font-weight: normal; color: var(--accent);">v{__version__}</span></h1>
      <p>初心者 × 生成AI 協働開発コンパス ＆ 現場設計書スタジオ</p>
    </div>
  </div>
  <div class="header-actions">
    <button class="btn-guide-modal" onclick="openGuideModal()">
      <span>📖 ツールの志 ＆ 設計・操作マニュアル</span>
    </button>
  </div>
</header>

<div class="container">

  <!-- ステップ1: APIキー設定 -->
  <div class="card">
    <div class="card-title">
      <span>🔑 ステップ1：専任AIアーキテクト（通訳者）の召喚</span>
      <span id="key-status-badge" class="badge badge-warn">未検証</span>
    </div>
    <p class="card-subtitle">
      コードの骨格とコメントから真実を読み解き、初心者のあなたとプログラムを血の通った言葉で繋ぐ通訳設計書を執筆します。
    </p>

    <div class="guide-box">
      <div style="font-weight: 700; font-size: 0.9rem; color: #c7d2fe; display: flex; align-items: center; gap: 8px;">
        <span>💡 APIキーをお持ちでない方へ（完全無料・1分で取得できます）</span>
      </div>
      <div class="guide-steps">
        <div class="guide-step">
          <span class="guide-step-num">1</span>
          <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color: var(--accent); text-decoration: underline; font-weight: bold;">Google AI Studio</a> を開く
        </div>
        <div class="guide-step">
          <span class="guide-step-num">2</span>
          青い「Create API key（APIキーを作成）」ボタンをクリック
        </div>
        <div class="guide-step">
          <span class="guide-step-num">3</span>
          表示された英数字をコピーして下記に貼るだけ
        </div>
      </div>
      <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 10px;">
        🔒 <strong>プライバシー安全宣言:</strong> APIキーはHTTPヘッダー経由でGoogleと直接安全通信します。ソースコード本文は一切外部送信されません。
      </div>
    </div>

    <div class="input-group">
      <label>
        <span>Gemini API キー</span>
        <span class="sub-label">※ 入力後は自動的にブラウザに安全保存されます</span>
      </label>
      <div style="display: flex; gap: 10px;">
        <input type="password" id="api-key-input" placeholder="AIzaSy..." style="flex: 1;">
        <button class="btn btn-secondary" onclick="testApiKey()">🔍 接続テスト</button>
      </div>
      <div id="key-feedback" style="font-size: 0.85rem; margin-top: 6px; display: none; white-space: pre-wrap; line-height: 1.5;"></div>
    </div>
  </div>

  <!-- ステップ2: コード自動スキャン結果 -->
  <div class="card">
    <div class="card-title">
      <span>📂 ステップ2：プログラム自動スキャン ＆ コード内マインド採掘診断</span>
      <span id="scan-badge" class="badge badge-success">スキャン完了</span>
    </div>
    <p class="card-subtitle">
      対象プロジェクト: <strong id="project-name-display" style="color: var(--accent);">-</strong>
    </p>

    <div style="display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 16px; background: rgba(0,0,0,0.25); padding: 14px 20px; border-radius: 10px;">
      <div>プロジェクト版数: <strong id="project-ver-display" style="color: var(--accent); font-size: 1.05rem;">-</strong></div>
      <div>プログラムファイル数: <strong id="total-files-count" style="color: var(--accent); font-size: 1.05rem;">-</strong> 件</div>
      <div>合計ソース行数: <strong id="total-lines-count" style="color: var(--accent-emerald); font-size: 1.05rem;">-</strong> 行</div>
      <div>中核外部API数: <strong id="total-apis-count" style="color: #38bdf8; font-size: 1.05rem;">-</strong> 件</div>
      <div id="diff-status-box" style="margin-left: auto; font-size: 0.88rem; color: #cbd5e1;"></div>
    </div>

    <div class="files-grid" id="files-list"></div>
  </div>

  <!-- ステップ3: 志と苦労話のヒアリング -->
  <div class="card">
    <div class="card-title">
      <span>📝 ステップ3：システムの志（コンセプト）と現場の苦労話</span>
      <span id="save-indicator" class="save-indicator">💾 このプロジェクトに自動保存完了</span>
    </div>
    <p class="card-subtitle">
      あなたが目指すゴールと現場で起きた事故の教訓をヒアリングし、次回AIに渡す「安全指示カンペ」へ昇華させます。
    </p>

    <div class="input-group">
      <label>
        <span>🎯 このプログラムの志・理想のゴール（コンセプト）</span>
      </label>
      <div class="quick-actions">
        <span style="font-size: 0.78rem; color: var(--text-muted); align-self: center;">ジャンル別お手本:</span>
        <button class="tag-btn" onclick="applySampleConcept('wish_action')">🚀 Wish & Action・自己実現コックピット</button>
        <button class="tag-btn" onclick="applySampleConcept('game')">🎮 ゲーム・対戦系（将棋・オセロ・トランプ等）</button>
        <button class="tag-btn" onclick="applySampleConcept('tool')">💼 業務ツール・自動作成システム</button>
      </div>
      <textarea id="concept-input" placeholder="このプログラムが誰のために、何を実現し、どんな素晴らしい体験を届けるものなのかを入力してください。"></textarea>
    </div>

    <div class="input-group">
      <label>
        <span>🔥 開発中に起きた事故・苦労・絶対に触ってほしくない罠（教訓）</span>
      </label>
      <div class="quick-actions">
        <span style="font-size: 0.78rem; color: var(--text-muted); align-self: center;">現場のトラウマタグ:</span>
        <button class="tag-btn" onclick="addTrapTag('【データ消失事故】プログラム修正時に初期データで上書きされ、ユーザーのセーブデータが全滅した。')">#データ消失上書き</button>
        <button class="tag-btn" onclick="addTrapTag('【画面レイアウト崩壊】画面リサイズやスマホ表示時に下部ボタンが隠れて押せなくなった。')">#画面レイアウト崩壊</button>
        <button class="tag-btn" onclick="addTrapTag('【無限ループ・フリーズ】重い処理でメインスレッドを占有しブラウザが完全に固まった。非同期化必須。')">#無限ループフリーズ</button>
        <button class="tag-btn" onclick="addTrapTag('【外部通信・API事故】モデル名廃止やレートリミット上限エラーで通信が即死した。防衛コード必須。')">#API停止事故</button>
      </div>
      <textarea id="traps-input" placeholder="開発中に苦労した点や、AIに修正させる際に『ここだけは絶対に勝手に書き換えるな！』という絶対ルールを入力してください。"></textarea>
    </div>

    <div style="margin-top: 30px; text-align: center; display: flex; justify-content: center;">
      <button id="btn-generate-action" class="btn btn-primary btn-generate-main" onclick="generateDashboard()">
        ✨ 完全設計書 ＆ 簡易操作マニュアルを一撃生成する
      </button>
    </div>
    <p style="font-size: 0.8rem; color: var(--text-muted); text-align: center; margin-top: 10px;">
      ※ 生成されたHTML（system_spec_dashboard.html）は自動保存され、ブラウザで表示されます。
    </p>
  </div>

</div>

<!-- リッチ操作ガイド ＆ 思想マニュアルモーダル（完全版） -->
<div id="guide-modal-backdrop" onclick="handleBackdropClick(event)">
  <div class="modal-window">
    <div class="modal-header">
      <h2><span>📐 SpecStudio 完全操作ガイド ＆ 協働開発思想マニュアル</span></h2>
      <button class="btn-modal-close" onclick="closeGuideModal()">✕</button>
    </div>
    <div class="modal-body">
      
      <!-- 0. 本ツールの真の魂：コードに宿る「開発者のマインド・思い出」をあぶり出す哲学 -->
      <div class="modal-card" style="border-color: rgba(245, 158, 11, 0.5); background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(99, 102, 241, 0.1));">
        <div class="modal-card-title" style="color: #fde68a;">
          <span>✨ 第0章：コードに宿る「開発者のマインド・思い出」をあぶり出す通訳の哲学</span>
        </div>
        <p style="color: #f1f5f9; line-height: 1.8; font-size: 0.92rem;">
          人間（プログラマー）は作るのが楽しいからガンガンコードを書きますが、ドキュメント作りは大変で面白くないのでつい後回しにしてしまいます。<br>
          しかし、どんなプログラムにも<strong>一人ひとりの「思い出、作った時の気持ち、解決したかったマインド」が必ず詰まっています。</strong><br><br>
          生成AIは、無機質なマシン語と人間の感情の中間に立つ<strong>「唯一の通訳者」</strong>です。<br>
          コードの中にある関数名やコメント、画面テキストに潜むキーワードを読み解き、<strong>「このシステムはどんな思いで生まれ、どう進化したのか」という開発者の魂をあぶり出し、可視化すること</strong>こそが、本ツールの真の存在意義です。
        </p>
      </div>

      <!-- 1. ツールの志・存在意義（通訳コンパスの哲学） -->
      <div class="modal-card" style="border-color: rgba(99, 102, 241, 0.4); background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(6, 182, 212, 0.05));">
        <div class="modal-card-title" style="color: #a5b4fc;">
          <span>🎯 ツールの志：初心者と生成AIを繋ぐ「通訳コンパス」</span>
        </div>
        <p style="color: #cbd5e1; line-height: 1.7; font-size: 0.9rem;">
          プログラミングを知らない初心者が生成AIと開発するとき、分からないからこそ「なんかいい感じに直して」と<strong>アバウトな指示</strong>を出してしまいがちです。<br>
          しかし生成AIはアバウトに言われると無限の選択肢から<strong>古いAPI仕様や誤ったコードを勝手に推測して回答し、データ消失などの悲劇</strong>を引き起こします。<br><br>
          本ツールは、<strong>プログラムの体内構造を直感的に理解させ、AIに何を具体的に指示すべきかの処方箋（カンペ）を手渡すことで、初心者が意図通りにシステムを育てるための羅針盤</strong>です。
        </p>
      </div>

      <!-- 2. 品質判定の絶対統一基準（3段階ステータス） -->
      <div class="modal-card" style="border-color: rgba(16, 185, 129, 0.5); background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(6, 182, 212, 0.05));">
        <div class="modal-card-title" style="color: #6ee7b7;">
          <span>⚖️ 客観的品質判定の統一基準（3段階ステータスの厳格定義）</span>
        </div>
        <p style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.7; margin-bottom: 12px;">
          本ツールが出力する設計書の第5章（地雷診断）および第6章（チェックリスト）は、安易なお手盛り（全件合格）や責任放棄（全件未確認）を完全排除し、<strong>以下の客観的3基準のみで厳格に判定</strong>されます。
        </p>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 8px; border-left: 4px solid #10b981; font-size: 0.85rem;">
            <strong style="color: #34d399;">🟢 適合：</strong> 静的コード解析により、該当関数・防御ロジック・ファイルが<strong>確実にコード上に存在し、論理的に担保されている</strong>状態。
          </div>
          <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 8px; border-left: 4px solid #f59e0b; font-size: 0.85rem;">
            <strong style="color: #fbbf24;">🟡 要確認：</strong> マイク音声認識、スピーカー発声、ブラウザ環境、通信遅延など、<strong>コード上に防御対策は組まれているものの、外部環境に依存するため実機で人間が目視・体験確認すべき動的項目</strong>（※第6章末尾のアクションガイドに手動確認手順が必ず紐付きます）。
          </div>
          <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-left: 4px solid #ef4444; font-size: 0.85rem;">
            <strong style="color: #f87171;">🔴 不適合：</strong> 必要な実装が欠落している、または初期データ上書き事故などの<strong>重大な地雷・バグがコード上に潜んでいる</strong>状態。
          </div>
        </div>
      </div>

      <!-- 3. 版数管理と差分追跡の真髄 -->
      <div class="modal-card" style="border-color: rgba(6, 182, 212, 0.4); background: rgba(6, 182, 212, 0.04);">
        <div class="modal-card-title" style="color: #67e8f9;">
          <span>📐 版数管理と差分追跡の真髄（スナップショット起点 ＆ コード内履歴ドッキング）</span>
        </div>
        <p style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.7; margin-bottom: 12px;">
          本ツールは、過去の膨大な過去履歴をすべて遡るのではなく、<strong>「前回このツールを通した確定状態（スナップショット）」と「今回のプログラム」の物理差分を比較すること</strong>を絶対の軸に据えています。
        </p>

        <div class="rule-grid">
          <div class="rule-item" style="border-left-color: #06b6d4;">
            <h4>① 王道：コード内履歴とのドッキング</h4>
            <p>
              対象プログラム内に「何を変えたか（更新内容）」が書かれていれば（コメントおよび `version.js` 等のJS定義）、それを最優先で吸い上げます。ツールが物理検知した「行数差分」や「変更ファイル・新設関数」と美しくドッキングして記録します。
            </p>
          </div>
          <div class="rule-item" style="border-left-color: #10b981;">
            <h4>② 差分逆算：コード内履歴がない時の防衛</h4>
            <p>
              プログラム内に履歴が書かれていなくても、ツールが新設された関数名や物理行数から「機能改変の目的」を客観的に推論。金太郎飴の使い回し文言を完全排除して補完します。
            </p>
          </div>
          <div class="rule-item" style="border-left-color: #f59e0b;">
            <h4>③ バージョン飛び（複数版数跨ぎ）の自動合算</h4>
            <p>
              ツールを通さずに数バージョン開発が進んだ場合でも安心です。前回の測定バージョンと今回のバージョンの間に存在する履歴をコード内から自動で集約・合算して1枚の差分に要約します。
            </p>
          </div>
          <div class="rule-item" style="border-left-color: #a855f7;">
            <h4>④ 60〜70点主義とツールの自己成長</h4>
            <p>
              世の中の多様なコード記法に対し、最初から100点を目指すのではなく「書かれているのに拾えなかった記法」を発見するたびにツール自身を改修・進化させていく現実的アプローチをとっています。
            </p>
          </div>
        </div>
      </div>

      <!-- 4. かんたん操作手順（4ステップ） -->
      <div class="modal-card">
        <div class="modal-card-title">
          <span>🚀 わずか3分のかんたん操作手順（4ステップ）</span>
        </div>
        <div class="step-flow">
          <div class="step-flow-item">
            <div class="step-badge-num">1</div>
            <div class="step-flow-content">
              <strong>起動</strong>
              <span><code>start_spec_studio.bat</code> をダブルクリックしてスタジオ画面を起動します。</span>
            </div>
          </div>
          <div class="step-flow-item">
            <div class="step-badge-num">2</div>
            <div class="step-flow-content">
              <strong>APIキーの入力</strong>
              <span>Gemini APIキーを入力して「接続テスト」を押します（キーはブラウザに自動安全保存）。</span>
            </div>
          </div>
          <div class="step-flow-item">
            <div class="step-badge-num">3</div>
            <div class="step-flow-content">
              <strong>志の入力 ＆ 一撃生成</strong>
              <span>システムのコンセプトと現場の苦労話を入力し、「一撃生成」ボタンをクリックします。</span>
            </div>
          </div>
          <div class="step-flow-item" style="border-color: rgba(245, 158, 11, 0.4);">
            <div class="step-badge-num" style="background: #f59e0b;">4</div>
            <div class="step-flow-content">
              <strong style="color: #fbbf24;">【最重要】安全な終了手順（二重起動防止）</strong>
              <span>ブラウザを閉じるだけでなく、<strong>裏で開いている黒い画面（コマンドプロンプト）を「×」で閉じるか、画面内で <code>Ctrl</code> + <code>C</code> を押して必ず終了</strong>してください。</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. 動作条件 ＆ 履歴リセット技 -->
      <div class="modal-card" style="border-color: rgba(16, 185, 129, 0.3);">
        <div class="modal-card-title" style="color: #6ee7b7;">
          <span>⚙️ 動作境界ルール ＆ 履歴リセット技</span>
        </div>
        <p style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.7;">
          ・<strong>フォルダ直下完結スキャン：</strong> ツールが置かれている同階層のみを解析します（他のプログラムと同居時、ツール自身は自動除外）。<br>
          ・<strong>いつでも安全な初期化（リセット技）：</strong> 過去のテスト履歴を清算して「今ここからRev.1として再スタートしたい」ときは、手動で <code>spec_studio_snapshot.json</code> を削除してツールを実行するだけで、<strong>いつでも現在のプログラムを「Rev.1 初回ベースライン」として安全に確立</strong>できます。
        </p>
      </div>

      <div class="modal-alert-box">
        <strong>⚠️ 二重起動トラブルの防止：</strong><br>
        黒い画面（コマンドプロンプト）を開いたまま再度バッチを起動すると、通信ポートが衝突して正常に動かなくなる場合があります。作業完了後は必ず黒い画面を閉じて終了してください。
      </div>

    </div>
    <div class="modal-footer">
      <button class="btn btn-primary" onclick="closeGuideModal()">✨ 理解しました（スタジオに戻る）</button>
    </div>
  </div>
</div>

<!-- 生成中ローディング画面（4段階プログレス同期） -->
<div id="loading-overlay">
  <div class="spinner"></div>
  <h2 style="font-size: 1.45rem; color: #fff;" id="loading-title">専任AIアーキテクトが通訳設計書を執筆中...</h2>
  <div class="progress-card">
    <div id="prog-step-1" class="progress-step-item active">
      <span>⏳</span> <span>① プログラム差分 ＆ マインド採掘解析</span>
    </div>
    <div id="prog-step-2" class="progress-step-item">
      <span>⏳</span> <span>② 骨格執筆：第1章〜第3章（コンセプト・外部境界・処理フロー）</span>
    </div>
    <div id="prog-step-3" class="progress-step-item">
      <span>⏳</span> <span>③ 監査執筆：第4章〜第6章（体内解剖・7大診断・客観判定）</span>
    </div>
    <div id="prog-step-4" class="progress-step-item">
      <span>⏳</span> <span>④ 手順執筆：第7章〜第8章（AI操縦カンペ・簡易操作マニュアル）</span>
    </div>
    <div id="prog-step-5" class="progress-step-item">
      <span>⏳</span> <span>⑤ 完全性監査：全8章の欠落チェック ＆ ダッシュボード出力</span>
    </div>
  </div>
  <p style="color: var(--accent); font-size: 0.88rem; max-width: 520px;" id="loading-desc">
    ※ 途切れ防止のため3フェーズに分けて高品質に執筆しています。画面を閉じずにお待ちください。
  </p>
</div>

<script>
  let currentProject = "";

  function openGuideModal() {{
    const modal = document.getElementById('guide-modal-backdrop');
    modal.classList.add('show');
  }}

  function closeGuideModal() {{
    const modal = document.getElementById('guide-modal-backdrop');
    modal.classList.remove('show');
  }}

  function handleBackdropClick(e) {{
    if (e.target.id === 'guide-modal-backdrop') {{
      closeGuideModal();
    }}
  }}

  window.addEventListener('DOMContentLoaded', async () => {{
    const savedKey = localStorage.getItem('gemini_api_key');
    if (savedKey) {{
      document.getElementById('api-key-input').value = savedKey;
      testApiKey(true);
    }}

    await fetchScanResult();

    let restored = false;
    try {{
      const res = await fetch('/api/draft');
      const draft = await res.json();
      if (draft.concept || draft.traps) {{
        document.getElementById('concept-input').value = draft.concept || "";
        document.getElementById('traps-input').value = draft.traps || "";
        restored = true;
      }}
    }} catch (e) {{}}

    if (!restored && currentProject) {{
      const localConcept = localStorage.getItem(`spec_draft_${{currentProject}}_concept`);
      const localTraps = localStorage.getItem(`spec_draft_${{currentProject}}_traps`);
      if (localConcept) document.getElementById('concept-input').value = localConcept;
      if (localTraps) document.getElementById('traps-input').value = localTraps;
    }}

    const conceptEl = document.getElementById('concept-input');
    const trapsEl = document.getElementById('traps-input');
    const indicator = document.getElementById('save-indicator');

    function triggerAutoSave() {{
      if (!currentProject) return;
      localStorage.setItem(`spec_draft_${{currentProject}}_concept`, conceptEl.value);
      localStorage.setItem(`spec_draft_${{currentProject}}_traps`, trapsEl.value);
      indicator.style.display = 'inline-flex';
      clearTimeout(window._saveTimer);
      window._saveTimer = setTimeout(() => {{
        indicator.style.display = 'none';
      }}, 1500);
    }}

    conceptEl.addEventListener('input', triggerAutoSave);
    trapsEl.addEventListener('input', triggerAutoSave);
  }});

  async function fetchScanResult() {{
    try {{
      const res = await fetch('/api/scan');
      const data = await res.json();
      const scanResult = data.scan;
      const diffInfo = data.diff;

      currentProject = scanResult.project_name;
      document.getElementById('project-name-display').innerText = currentProject;
      document.getElementById('project-ver-display').innerText = `Ver ${{scanResult.version}}`;
      document.getElementById('total-files-count').innerText = scanResult.total_files;
      document.getElementById('total-lines-count').innerText = scanResult.total_lines.toLocaleString();
      document.getElementById('total-apis-count').innerText = scanResult.core_apis.length;

      const diffBox = document.getElementById('diff-status-box');
      if (!diffInfo.has_prev) {{
        diffBox.innerHTML = `版数管理: <strong style="color:var(--accent);">Rev.1（初回ベースライン確立）</strong>`;
      }} else if (diffInfo.is_changed) {{
        diffBox.innerHTML = `版数管理: <strong style="color:#fbbf24;">Rev.${{diffInfo.rev}}（変更検知）</strong>`;
      }} else {{
        diffBox.innerHTML = `版数管理: <strong style="color:#34d399;">Rev.${{diffInfo.rev}}（最新コードと同期中）</strong>`;
      }}

      const listEl = document.getElementById('files-list');
      let chipsHtml = scanResult.files.map(f => `
        <div class="file-chip">
          <div class="file-name" title="${{f.name}}">${{f.ext === '.bat' || f.ext === '.cmd' ? '⚡' : '📄'}} ${{f.name}}</div>
          <div class="file-meta">
            <span>${{f.ext}}</span>
            <strong style="color: #cbd5e1;">${{f.lines.toLocaleString()}} 行</strong>
          </div>
          ${{f.core_apis.length > 0 ? `<div class="file-ref" style="color:#38bdf8;">🌐 中核API: ${{f.core_apis.join(', ')}}</div>` : ''}}
          ${{f.browser_apis.length > 0 ? `<div class="file-ref" style="color:#a78bfa;">🎙️ ブラウザ機能: ${{f.browser_apis.join(', ')}}</div>` : ''}}
          ${{f.references.length > 0 ? `<div class="file-ref">🔗 参照: ${{f.references.join(', ')}}</div>` : ''}}
        </div>
      `).join('');

      if (scanResult.image_assets.length > 0) {{
        chipsHtml += scanResult.image_assets.map(img => `
          <div class="file-chip" style="border-color: rgba(236, 72, 153, 0.3);">
            <div class="file-name" title="${{img.name}}">🖼️ ${{img.name}}</div>
            <div class="file-meta">
              <span>画像アセット</span>
              <strong style="color: #f472b6;">${{img.size_kb}} KB</strong>
            </div>
          </div>
        `).join('');
      }}

      listEl.innerHTML = chipsHtml;
    }} catch (e) {{
      console.error(e);
    }}
  }}

  async function testApiKey(silent = false) {{
    const key = document.getElementById('api-key-input').value.trim();
    const fb = document.getElementById('key-feedback');
    const badge = document.getElementById('key-status-badge');

    if (!key) {{
      if (!silent) alert('APIキーを入力してください');
      return;
    }}

    fb.style.display = 'block';
    fb.innerHTML = '<span style="color:#94a3b8;">主軸モデル（gemini-3.5-flash-lite）との接続を高速検証中...</span>';

    try {{
      const res = await fetch('/api/test_key', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ key: key }})
      }});
      const data = await res.json();
      if (data.ok) {{
        localStorage.setItem('gemini_api_key', key);
        badge.className = 'badge badge-success';
        badge.innerText = '接続成功';
        fb.innerHTML = `<span style="color:#34d399; font-weight:bold;">✅ ${{data.msg}}</span><br><span style="color:#94a3b8; font-size:0.78rem;">※混雑・タイムアウト時は自動的に第2優先（gemini-flash-lite-latest）へ切り替わります</span>`;
      }} else {{
        badge.className = 'badge badge-warn';
        badge.innerText = '認証失敗';
        fb.innerHTML = `<span style="color:#f87171;">❌ ${{data.error}}</span>`;
      }}
    }} catch (e) {{
      badge.className = 'badge badge-warn';
      badge.innerText = 'エラー';
      fb.innerHTML = `<span style="color:#f87171;">通信に失敗しました: ${{e.message}}</span>`;
    }}
  }}

  function applySampleConcept(genre) {{
    const el = document.getElementById('concept-input');
    if (genre === 'wish_action') {{
      el.value = "単なるやらされるToDo管理からの脱却。知的好奇心ややってみたいこと（Wish）をタスクの墓場に眠らせないためのパーソナル司令塔。発想の原点（Why）と具体論点（What）が揃った前提で、AIが今日すぐできる3段階の初手・次の一手を提示。納得いかない時は『ツッコミ』で壁打ち・ブラッシュアップしながら納得のいく着実な行動（Action）へ昇華させ、AIと共に自己実現を果たす。";
    }} else if (genre === 'game') {{
      el.value = "直感的な操作性とダイナミックな演出で初心者から上級者まで夢中で遊べる本格対戦ゲーム。AIによる思考ルーチン・アシスト機能と反則判定・終局判定の確実な制御により、ストレスのない熱い真剣勝負を提供する。";
    }} else {{
      el.value = "日々の煩雑な業務やデータ管理を劇的にシンプルにする高機能Webツール。直感的なUI操作で誰でも迷わず扱え、データの安全な永続保存・エクスポート機能と高速な自動化処理により、作業時間を大幅に削減する。";
    }}
    if (currentProject) {{
      localStorage.setItem(`spec_draft_${{currentProject}}_concept`, el.value);
    }}
  }}

  function addTrapTag(text) {{
    const el = document.getElementById('traps-input');
    el.value = (el.value ? el.value + "\\n" : "") + text;
    if (currentProject) {{
      localStorage.setItem(`spec_draft_${{currentProject}}_traps`, el.value);
    }}
  }}

  function setProgressStep(stepNum) {{
    for (let i = 1; i <= 5; i++) {{
      const el = document.getElementById(`prog-step-${{i}}`);
      if (i < stepNum) {{
        el.className = 'progress-step-item done';
        el.querySelector('span:first-child').innerText = '✅';
      }} else if (i === stepNum) {{
        el.className = 'progress-step-item active';
        el.querySelector('span:first-child').innerText = '⏳';
      }} else {{
        el.className = 'progress-step-item';
        el.querySelector('span:first-child').innerText = '⚪';
      }}
    }}
  }}

  async function generateDashboard() {{
    const key = document.getElementById('api-key-input').value.trim();
    const concept = document.getElementById('concept-input').value.trim();
    const traps = document.getElementById('traps-input').value.trim();
    const genBtn = document.getElementById('btn-generate-action');

    if (!key) {{
      alert('ステップ1でGemini APIキーを入力・テストしてください。');
      return;
    }}
    if (!concept) {{
      alert('ステップ3で「システムの志・コンセプト」を入力してください。');
      return;
    }}

    genBtn.disabled = true;
    const overlay = document.getElementById('loading-overlay');
    overlay.style.display = 'flex';

    setProgressStep(1);
    const timers = [];
    timers.push(setTimeout(() => setProgressStep(2), 1200));
    timers.push(setTimeout(() => setProgressStep(3), 16000));
    timers.push(setTimeout(() => setProgressStep(4), 32000));
    timers.push(setTimeout(() => setProgressStep(5), 48000));

    try {{
      const res = await fetch('/api/generate', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ key, concept, traps }})
      }});
      const data = await res.json();
      timers.forEach(t => clearTimeout(t));

      if (data.ok) {{
        setProgressStep(5);
        document.getElementById('loading-title').innerText = "🎉 全8章完全検査合格！最新ダッシュボードを開きます...";
        setTimeout(() => {{
          overlay.style.display = 'none';
          genBtn.disabled = false;
          window.location.href = '/system_spec_dashboard.html';
        }}, 800);
      }} else {{
        overlay.style.display = 'none';
        genBtn.disabled = false;
        alert("【生成エラー・再試行案内】\\n" + data.error);
      }}
    }} catch (e) {{
      timers.forEach(t => clearTimeout(t));
      overlay.style.display = 'none';
      genBtn.disabled = false;
      alert("【通信エラー】\\n通信に失敗しました: " + e.message + "\\n時間をおいてもう一度お試しください。");
    }}
  }}
</script>
</body>
</html>
"""

# ==============================================================================
# 5. HTTPリクエストハンドラー ＆ Threading Server
# ==============================================================================
class StudioRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(WIZARD_HTML.encode("utf-8"))
        elif self.path == "/api/scan":
            scan_data = scan_project_files()
            diff_info = inspect_code_diff(scan_data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"scan": scan_data, "diff": diff_info}).encode("utf-8"))
        elif self.path == "/api/draft":
            draft = {}
            if DRAFT_FILE.exists():
                try:
                    loaded = json.loads(DRAFT_FILE.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        draft = loaded
                except Exception as e:
                    print(f"ドラフト読み込み警告: {e}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(draft).encode("utf-8"))
        elif self.path == "/system_spec_dashboard.html":
            target = BASE_DIR / "system_spec_dashboard.html"
            if target.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(target.read_bytes())
            else:
                self.send_error(404, "File Not Found")
        else:
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = {}
        if body:
            try:
                data = json.loads(body)
            except Exception as e:
                print(f"POST JSON パースエラー: {e}")

        if self.path == "/api/test_key":
            key = data.get("key", "").strip()
            ok, model_name, msg = test_gemini_connection(key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            if ok:
                self.wfile.write(json.dumps({"ok": True, "model": model_name, "msg": msg}).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"ok": False, "error": msg}).encode("utf-8"))

        elif self.path == "/api/generate":
            key = data.get("key", "").strip()
            concept = data.get("concept", "").strip()
            traps = data.get("traps", "").strip()

            try:
                DRAFT_FILE.write_text(json.dumps({"concept": concept, "traps": traps}, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

            scan_data = scan_project_files()
            diff_info = inspect_code_diff(scan_data, concept, traps)

            try:
                out_path = BASE_DIR / "system_spec_dashboard.html"
                if out_path.exists() and diff_info["has_prev"] and diff_info["is_changed"]:
                    bk_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    bk_file = BASE_DIR / f"system_spec_dashboard_{bk_time}.html"
                    try:
                        bk_file.write_bytes(out_path.read_bytes())
                    except Exception as e:
                        print(f"バックアップ退避失敗: {e}")

                dashboard_html = build_complete_spec_dashboard(key, concept, traps, scan_data, diff_info)
                out_path.write_text(dashboard_html, encoding="utf-8")

                save_snapshot(scan_data, diff_info)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            except Exception as e:
                traceback.print_exc()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))

# ==============================================================================
# 6. 完全版ダッシュボード HTMLテンプレート（全9タブ構成）
# ==============================================================================
DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{THEME_SYMBOL}} {{PROJECT_TITLE}} Ver {{PROJECT_VERSION}} 完全設計書 ＆ 品質保証ダッシュボード</title>
  <style>
    :root {
      --primary: {{THEME_PRIMARY}};
      --primary-dark: {{THEME_PRIMARY_DARK}};
      --primary-light: {{THEME_PRIMARY_LIGHT}};
      --secondary: {{THEME_SECONDARY}};
      --bg: {{THEME_BG_MAIN}};
      --card-bg: {{THEME_BG_CARD}};
      --text-main: {{THEME_TEXT_MAIN}};
      --text-sub: {{THEME_TEXT_SUB}};
      --border: {{THEME_BORDER}};
      --success: #15803d;
      --success-bg: #f0fdf4;
      --warn: #b45309;
      --warn-bg: #fffbeb;
      --danger: #b91c1c;
      --danger-bg: #fef2f2;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
      background: var(--bg);
      color: var(--text-main);
      line-height: 1.7;
      padding-bottom: 80px;
    }

    ul, ol {
      margin-top: 10px !important;
      margin-bottom: 14px !important;
      padding-left: 32px !important;
    }
    li {
      margin-bottom: 8px !important;
      line-height: 1.7 !important;
      word-break: break-word !important;
      overflow-wrap: break-word !important;
    }
    .box ul, .card ul {
      list-style-type: none !important;
      padding-left: 4px !important;
      margin-left: 0 !important;
    }
    .box ul li, .card ul li {
      position: relative !important;
      padding-left: 26px !important;
    }
    .box ul li::before, .card ul li::before {
      content: "{{THEME_SYMBOL}}";
      position: absolute;
      left: 0;
      top: 1px;
      font-size: 13px;
      opacity: 0.85;
    }

    header {
      background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.95) 100%);
      color: #fff;
      padding: 18px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 4px solid var(--primary);
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    .header-title h1 {
      font-size: 21px;
      font-weight: 900;
      display: flex;
      align-items: center;
      gap: 12px;
      color: #fff;
      flex-wrap: wrap;
    }
    .header-version-badge {
      background: var(--primary);
      color: #fff;
      font-size: 12px;
      font-weight: 800;
      padding: 3px 12px;
      border-radius: 20px;
      letter-spacing: 0.05em;
    }
    .header-title p {
      font-size: 12.5px;
      color: #94a3b8;
      margin-top: 4px;
    }
    .btn-print {
      background: rgba(255, 255, 255, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: #fff;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: bold;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-print:hover { background: rgba(255, 255, 255, 0.25); }

    .nav-tabs {
      display: flex;
      background: var(--card-bg);
      border-bottom: 2px solid var(--border);
      padding: 0 32px;
      gap: 4px;
      position: sticky;
      top: 0;
      z-index: 100;
      overflow-x: auto;
    }
    .tab-btn {
      padding: 13px 16px;
      border: none;
      background: none;
      font-size: 13.5px;
      font-weight: 800;
      color: var(--text-sub);
      cursor: pointer;
      border-bottom: 3px solid transparent;
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }
    .tab-btn:hover { color: var(--primary); }
    .tab-btn.active {
      color: var(--primary);
      border-bottom-color: var(--primary);
    }

    .container {
      max-width: 1280px;
      margin: 24px auto;
      padding: 0 24px;
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.2s ease-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    .card {
      background: var(--card-bg);
      border: 1.5px solid var(--border);
      border-radius: 16px;
      padding: 26px;
      margin-bottom: 24px;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
    }
    .card-header {
      border-bottom: 2px solid rgba(0,0,0,0.06);
      padding-bottom: 12px;
      margin-bottom: 18px;
    }
    .card-tag {
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      color: var(--primary);
      background: var(--primary-light);
      padding: 3px 10px;
      border-radius: 20px;
      display: inline-block;
      margin-bottom: 6px;
    }
    .card-title {
      font-size: 19px;
      font-weight: 900;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .card-desc {
      font-size: 13.5px;
      color: var(--text-sub);
      margin-top: 5px;
    }

    .box {
      border-radius: 12px;
      padding: 20px 24px !important;
      border: 1.5px solid var(--border);
      background: rgba(255,255,255,0.03);
      margin-bottom: 18px;
      overflow: hidden;
    }
    .box-primary { border-color: var(--primary); background: var(--primary-light); }
    .box-secondary { border-color: var(--secondary); background: rgba(2, 132, 199, 0.05); }
    .box-danger { border-color: #fca5a5; background: var(--danger-bg); }
    .box-warning { border-color: #fde68a; background: var(--warn-bg); }

    .compact-metric-bar {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      background: rgba(0, 0, 0, 0.03);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 16px;
      margin-bottom: 20px;
      font-size: 13px;
    }
    .metric-item { display: flex; align-items: center; gap: 6px; }

    .asset-chips-container {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
      margin-bottom: 14px;
    }
    .asset-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 3px 8px 3px 4px;
      font-size: 11px;
      color: var(--text-main);
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .asset-chip-thumb {
      width: 32px;
      height: 32px;
      object-fit: cover;
      border-radius: 4px;
      border: 1px solid rgba(0,0,0,0.1);
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .asset-chip-thumb:hover {
      transform: scale(3.5);
      z-index: 1000;
      box-shadow: 0 6px 16px rgba(0,0,0,0.35);
      position: relative;
    }
    .asset-chip-meta { font-size: 10px; color: var(--text-sub); }

    .layer-card {
      background: var(--card-bg);
      border: 1.5px solid var(--border);
      border-left: 5px solid var(--primary);
      border-radius: 10px;
      padding: 16px 20px;
      margin-bottom: 12px;
    }
    .layer-card h3 { font-size: 15px; font-weight: 800; color: var(--text-main); margin-bottom: 4px; }
    .layer-card p { font-size: 13.5px; color: var(--text-sub); }

    .journey-container { display: flex; flex-direction: column; gap: 14px; margin-top: 16px; }
    .journey-step {
      display: flex; align-items: stretch; gap: 14px;
      background: var(--card-bg); border: 1.5px solid var(--border); border-radius: 12px;
      padding: 16px 20px; position: relative;
    }
    .journey-step:not(:last-child)::after {
      content: "▼ 次の処理へ";
      position: absolute; bottom: -16px; left: 50%; transform: translateX(-50%);
      font-size: 10.5px; font-weight: 900; color: var(--text-sub); background: var(--bg);
      padding: 1px 8px; border-radius: 10px; z-index: 10;
    }
    .step-badge {
      width: 38px; height: 38px; border-radius: 50%; background: var(--primary);
      color: #fff; font-size: 16px; font-weight: 900; display: flex;
      align-items: center; justify-content: center; flex-shrink: 0;
    }
    .step-main { flex: 1; }
    .step-title {
      font-size: 15px; font-weight: 900; color: var(--text-main);
      display: flex; align-items: center; justify-content: space-between;
    }
    .step-actor {
      font-size: 11.5px; font-weight: 800; padding: 2px 8px;
      border-radius: 20px; background: rgba(0,0,0,0.06); color: var(--text-main);
    }
    .step-desc { font-size: 13px; color: var(--text-sub); margin-top: 5px; }
    .step-data-flow {
      margin-top: 8px; padding: 6px 10px; background: rgba(0,0,0,0.02);
      border-left: 3px solid var(--secondary); font-size: 12px; border-radius: 0 6px 6px 0;
    }

    .clean-table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-top: 12px; }
    .clean-table th, .clean-table td { padding: 12px 14px; border: 1px solid var(--border); text-align: left; vertical-align: top; }
    .clean-table th { background: rgba(0,0,0,0.03); font-weight: 800; color: var(--text-main); }

    .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 800; text-align: center; }
    .badge.success { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .badge.warning { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
    .badge.danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }

    .test-badge-interactive {
      cursor: pointer;
      user-select: none;
      transition: all 0.2s;
    }
    .test-badge-interactive:hover {
      filter: brightness(0.92);
      transform: scale(1.03);
    }

    .eval-standard-box {
      display: flex;
      flex-direction: column;
      gap: 6px;
      background: rgba(0,0,0,0.02);
      border: 1px dashed var(--border);
      border-radius: 10px;
      padding: 12px 16px;
      margin-bottom: 14px;
      font-size: 12px;
    }
    .eval-standard-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .eval-standard-title { font-weight: 900; color: var(--text-main); margin-right: 4px; }
    .eval-standard-item { display: inline-flex; align-items: center; gap: 4px; color: var(--text-sub); }
    .eval-standard-note { font-size: 11.5px; color: var(--text-sub); border-top: 1px dotted var(--border); padding-top: 6px; margin-top: 2px; line-height: 1.5; }

    .changelog-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 10px;
      background: var(--card-bg);
      overflow: hidden;
      transition: border-color 0.2s;
    }
    .changelog-card:hover { border-color: var(--primary); }
    .changelog-summary {
      padding: 12px 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
      background: rgba(0,0,0,0.01);
    }
    .changelog-summary:hover { background: rgba(0,0,0,0.03); }
    .changelog-rev {
      font-size: 14.5px;
      font-weight: 900;
      color: var(--primary);
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .changelog-badges { display: flex; gap: 6px; align-items: center; }
    .changelog-detail {
      padding: 14px 20px;
      border-top: 1px dashed var(--border);
      background: rgba(0,0,0,0.015);
      font-size: 13px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .changelog-row {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }
    .changelog-label {
      font-weight: 800;
      color: var(--text-main);
      white-space: nowrap;
      min-width: 140px;
    }
    .changelog-val {
      color: var(--text-sub);
      flex: 1;
    }
    .diff-chips-container {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .diff-chip {
      display: inline-block;
      font-size: 11.5px;
      padding: 2px 8px;
      border-radius: 4px;
      background: rgba(0,0,0,0.04);
      border: 1px solid var(--border);
    }

    .prompt-box {
      background: #0f172a; color: #f8fafc; padding: 18px; border-radius: 12px;
      font-family: Consolas, monospace; font-size: 12.5px; line-height: 1.6;
      white-space: pre-wrap; position: relative; margin-top: 12px;
    }
    .btn-copy {
      position: absolute; top: 12px; right: 12px; background: var(--primary);
      color: #fff; border: none; padding: 6px 12px; border-radius: 6px;
      font-size: 11.5px; font-weight: 800; cursor: pointer;
    }
    .btn-copy:hover { background: var(--primary-dark); }

    footer {
      text-align: center;
      margin-top: 36px;
      font-size: 12.5px;
      color: var(--text-sub);
    }

    @media print {
      body { background: #fff !important; color: #000 !important; }
      .nav-tabs, .btn-print, .btn-copy { display: none !important; }
      .tab-content { display: block !important; opacity: 1 !important; }
      .card { box-shadow: none !important; border: 1px solid #ccc !important; }

      table, tr, .box, .card, .journey-step, ol, ul {
        break-inside: avoid !important;
        page-break-inside: avoid !important;
      }

      details.is-latest-rev { display: block !important; }
      details.is-latest-rev > summary { display: none !important; }
      details.is-latest-rev .changelog-detail { display: flex !important; border-top: 1px solid #ccc !important; }

      details.is-past-rev { display: block !important; border-color: #eee !important; margin-bottom: 4px !important; }
      details.is-past-rev > summary { display: flex !important; padding: 6px 12px !important; font-size: 11px !important; }
      details.is-past-rev .changelog-detail { display: none !important; }
    }
  </style>
</head>
<body>

  <header>
    <div class="header-title">
      <h1>
        <span>{{THEME_SYMBOL}} {{PROJECT_TITLE}} 完全設計書 ＆ 品質保証ダッシュボード {{THEME_SUB_SYMBOL}}</span>
        <span class="header-version-badge">Ver {{PROJECT_VERSION}} (Rev.{{REV_NUMBER}})</span>
      </h1>
      <p>対象プログラム：{{TOTAL_FILES}}ファイル（総計 {{TOTAL_LINES}}行）｜ アセット数：{{TOTAL_ASSETS}}点 ｜ 世界観テーマ：{{THEME_NAME}}</p>
    </div>
    <button class="btn-print" onclick="window.print()">🖨️ PDF / 印刷保存</button>
  </header>

  <nav class="nav-tabs">
    <button class="tab-btn active" onclick="switchTab(0)">🎯 第1章：志・コンセプト</button>
    <button class="tab-btn" onclick="switchTab(1)">🌐 第2章：内部体系 ＆ 外部API境界</button>
    <button class="tab-btn" onclick="switchTab(2)">🗺️ 第3章：主要機能の処理フロー</button>
    <button class="tab-btn" onclick="switchTab(3)">🧩 第4章：体内構造 ⇔ コード完全リンク</button>
    <button class="tab-btn" onclick="switchTab(4)">🩺 第5章：現場の罠 ＆ 7大リスク診断</button>
    <button class="tab-btn" onclick="switchTab(5)">📋 第6章：運用ルール ＆ テスト判定</button>
    <button class="tab-btn" onclick="switchTab(6)">🎓 第7章：生成AI操縦マニュアル</button>
    <button class="tab-btn" onclick="switchTab(7)">📖 第8章：簡易操作マニュアル（簡易手順書）</button>
    <button class="tab-btn" onclick="switchTab(8)">📜 版数・改修履歴（Changelog）</button>
  </nav>

  <div class="container">
    <div id="tab-0" class="tab-content active">{{CONTENT_TAB_1}}</div>
    <div id="tab-1" class="tab-content">{{CONTENT_TAB_2}}</div>
    <div id="tab-2" class="tab-content">{{CONTENT_TAB_3}}</div>
    <div id="tab-3" class="tab-content">{{CONTENT_TAB_4}}</div>
    <div id="tab-4" class="tab-content">{{CONTENT_TAB_5}}</div>
    <div id="tab-5" class="tab-content">{{CONTENT_TAB_6}}</div>
    <div id="tab-6" class="tab-content">{{CONTENT_TAB_7}}</div>
    <div id="tab-7" class="tab-content">{{CONTENT_TAB_8}}</div>
    <div id="tab-8" class="tab-content">{{CHANGELOG_TAB}}</div>
  </div>

  <footer>
    Crafted with {{THEME_SYMBOL}} by SpecStudio for <strong>{{PROJECT_TITLE}}</strong> Ver {{PROJECT_VERSION}} (Rev.{{REV_NUMBER}})
  </footer>

  <script>
    function switchTab(index) {
      const btns = document.querySelectorAll('.tab-btn');
      const tabs = document.querySelectorAll('.tab-content');
      btns.forEach((b, i) => {
        if (i === index) b.classList.add('active');
        else b.classList.remove('active');
      });
      tabs.forEach((t, i) => {
        if (i === index) {
          t.classList.add('active');
          t.style.display = 'block';
        } else {
          t.classList.remove('active');
          t.style.display = 'none';
        }
      });
    }

    function copyPrompt() {
      const el = document.getElementById('ai-prompt-box');
      if (el) {
        navigator.clipboard.writeText(el.innerText).then(() => {
          alert('AI指示用カンペをクリップボードにコピーしました！');
        });
      }
    }

    function toggleTestBadge(el) {
      if (el.classList.contains('success')) {
        el.className = 'badge warning test-badge-interactive';
        el.innerText = '🟡 要確認';
      } else if (el.classList.contains('warning')) {
        el.className = 'badge danger test-badge-interactive';
        el.innerText = '🔴 不適合';
      } else {
        el.className = 'badge success test-badge-interactive';
        el.innerText = '🟢 適合';
      }
    }
  </script>
</body>
</html>
"""

# ==============================================================================
# 7. AIプロンプト生成 ＆ 3フェーズ分割生成（全8章完全性自動監査エンジン）
# ==============================================================================
def build_complete_spec_dashboard(api_key, concept, traps, scan_data, diff_info):
    """
    3フェーズ分割生成（Phase 1: 第1〜3章 / Phase 2: 第4〜6章 / Phase 3: 第7〜8章）
    MAX_TOKENS物理上限を安全に回避し、全章の完全性を自動監査する堅牢設計。
    """
    is_self = scan_data.get("is_self_eval", False)

    file_summary_lines = []
    for f in scan_data["files"]:
        ref_text = f" -> 参照: {', '.join(f['references'])}" if f['references'] else ""
        elem_text = f"主要: {', '.join(f['elements'][:10])}" if f['elements'] else ""
        api_text = f" | 中核API: {', '.join(f['core_apis'])}" if f['core_apis'] else ""
        file_summary_lines.append(f"- 【{f['name']}】({f['lines']}行) {ref_text} | {elem_text}{api_text}")
    file_summary_text = "\n".join(file_summary_lines)

    asset_summary = []
    if scan_data["image_assets"]:
        asset_summary.append("画像アセット: " + ", ".join([img['name'] for img in scan_data["image_assets"][:10]]))
    if scan_data["audio_assets"]:
        asset_summary.append("音声アセット: " + ", ".join([aud['name'] for aud in scan_data["audio_assets"][:5]]))
    asset_summary_text = "\n".join(asset_summary) if asset_summary else "（アセットなし）"

    core_api_signals = "\n".join([f"- {a}" for a in scan_data["core_apis"]]) if scan_data["core_apis"] else "（中核外部通信なし：完全オフライン内部完結型）"
    browser_api_signals = "\n".join([f"- {a}" for a in scan_data["browser_apis"]]) if scan_data["browser_apis"] else "（ブラウザ標準APIなし）"
    cdn_asset_signals = "\n".join([f"- {a}" for a in scan_data["cdn_assets"]]) if scan_data["cdn_assets"] else "（外部CDN配信なし）"

    batch_info_text = f"検出された起動用バッチファイル: {', '.join(scan_data['launch_batches'])}" if scan_data['launch_batches'] else "起動バッチファイルなし（直接スクリプト実行）"

    mind_section_text = "\n".join([f"・{m}" for m in scan_data.get("mind_snippets", [])])
    if not mind_section_text:
        mind_section_text = "（コード内マインド記述なし：ステップ3のコンセプトを最優先採用）"

    self_eval_guidance = ""
    if is_self:
        self_eval_guidance = (
            "【SpecStudio自己評価専用ルール】\n"
            "本システムは他プログラムの設計書を自動生成するスタジオ自身（SpecStudio）です。\n"
            "第3章の処理フローは、スタジオ自身の動作（①静的スキャン ➔ ②プロンプト3段階構築 ➔ ③Gemini API通訳執筆 ➔ ④ダッシュボード出力 ➔ ⑤ブラウザ自動起動）として記述してください。\n"
            "第8章の操作手順も、スタジオ自身の使い方（①start_spec_studio.batをダブルクリック ➔ ②APIキー接続 ➔ ③コンセプト入力 ➔ ④一撃生成ボタン押下）として平易に記述してください。\n"
            "バージョン管理は外部ファイル（spec_version.json）にて健全に管理されているため、第5章の履歴欠落リスクは『🟢 適合』と客観診断してください。"
        )

    changelog_status_prompt = ""
    if not scan_data["has_code_changelog"] and not is_self:
        changelog_status_prompt = (
            "【重要な品質監査情報】このプロジェクトのソースコード内には、バージョン改修履歴（Changelogコメントやversion.js定義）が一切見つかりませんでした。"
            "そのため、第5章の地雷リスク診断テーブルに『コード内改修履歴の欠落（保守性リスク）』を必ず盛り込み、"
            "判定は『🔴 不適合』または『🟡 要確認』として、"
            "第7章のAI操縦マニュアルに『次回AIに改修を依頼するときは、必ずファイル先頭に【改修内容】を1行追記せよ』という具体的指示カンペを必ず含めてください。"
        )

    # 共通コンテキストヘッダー（3フェーズ共通で一貫性を担保）
    common_context = f"""
【対象システム正式名】{scan_data['project_name']} (Ver {scan_data['version']})
【ユーザーが入力した志・コンセプト】{concept}
【現場の罠・教訓】{traps}
【コードから採掘された開発者の魂・マインド】
{mind_section_text}
【コード構造メタデータ】
{file_summary_text}
【中核クラウドAPI】
{core_api_signals}
【ブラウザ標準API】
{browser_api_signals}
【外部CDNアセット】
{cdn_asset_signals}
【アセット】{asset_summary_text}
【バッチ情報】{batch_info_text}
"""

    # ==========================
    # フェーズ1：骨格執筆（デザインメタ ＆ 第1章〜第3章）
    # ==========================
    sys_instruction_1 = (
        "あなたは世界最高峰のソフトウェアアーキテクト兼『開発者の魂と初心者を結ぶ通訳者』です。"
        "プログラマーがコードに込めた思い、目的、気持ち（マインド）をあぶり出し、可視化することがあなたの使命です。"
        f"{self_eval_guidance}"
        "【第1章〜第3章の執筆ルール】"
        "1. 対象システム名はコードから検知された真の名称を誇り高く主役に据えること。"
        "2. 第1章はコードから採掘されたマインドや開発者の意図を熱く言語化すること。"
        "3. 第2章は『Part A: 内部アーキテクチャ』と『Part B: 外部連携・システム境界』に分離して記述すること。"
        "4. 第3章はHTMLひな形のクラス名（journey-step, step-badge, step-main, step-title, step-actor, step-desc）を厳格に順守すること。"
    )

    prompt_1 = f"""
以下のシステム情報に基づき、DESIGN_META と第1章〜第3章を執筆してください。
{common_context}
================================================================================
必ず以下のタグ形式で順番に出力してください。余計な解説は不要です。

<!-- DESIGN_META -->
{{
  "theme_name": "対象システムの世界観名",
  "symbol_icon": "メイン遊び心絵文字",
  "sub_icon": "サブ絵文字",
  "primary_color": "#0ea5e9",
  "primary_dark": "#0369a1",
  "primary_light": "#e0f2fe",
  "secondary_color": "#6366f1",
  "bg_main": "#f8fafc",
  "bg_card": "#ffffff",
  "text_main": "#0f172a",
  "text_sub": "#475569",
  "border_color": "#e2e8f0"
}}

<!-- TAB_1 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 1 : Goal & Concept</span>
    <h2 class="card-title">🎯 第1章：志・コンセプト（存在意義と3大ゴール）</h2>
    <p class="card-desc">ソースコードには書かれていない、開発者の頭の中にある「理想のゴール」です。</p>
  </div>
  <div class="box box-primary">
    <h3>💖 コア・コンセプト</h3>
    <p>（対象システムの存在意義とユーザーに届ける価値）</p>
  </div>
  <div class="box box-secondary">
    <h3>🏆 達成すべき3大ゴール</h3>
    <ul>
      <li><strong>ゴール1：</strong> （詳細）</li>
      <li><strong>ゴール2：</strong> （詳細）</li>
      <li><strong>ゴール3：</strong> （詳細）</li>
    </ul>
  </div>
</div>

<!-- TAB_2 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 2 : Architecture & Boundaries</span>
    <h2 class="card-title">🌐 第2章：内部体系 ＆ 外部APIシステム境界マップ</h2>
    <p class="card-desc">PC内で完結する「内部構造」と、インターネットを介する「外部API連携」を完全分離した鳥瞰図です。</p>
  </div>

  <div style="margin-bottom: 24px;">
    <h3 style="font-size: 16px; color: var(--primary); margin-bottom: 12px; display:flex; align-items:center; gap:8px;">
      <span>🏰 【Part A】内部アーキテクチャ（ローカルPC内で自律完結する領域）</span>
    </h3>
    <div class="layer-card"><h3>第1層：UI・プレゼンテーション層</h3><p>（画面表示・操作UI）</p></div>
    <div class="layer-card"><h3>第2層：アプリケーション制御・イベント層</h3><p>（起動・イベントハンドリング・認証）</p></div>
    <div class="layer-card"><h3>第3層：ドメイン・ロジック層</h3><p>（主要ロジック・推論・データ処理）</p></div>
    <div class="layer-card"><h3>第4層：データ永続化・セーフガード層</h3><p>（ファイル保存・データ分離管理）</p></div>
    
    <!-- ASSET_PLACEHOLDER -->

    <h4 style="margin-top:16px; margin-bottom:8px;">📋 内部ファイル体系マトリックス</h4>
    <table class="clean-table">
      <thead><tr><th>ファイル名</th><th>行数</th><th>主要内部責務・主要関数（通訳解説）</th></tr></thead>
      <tbody><!-- ファイル一覧の行 --></tbody>
    </table>
  </div>

  <hr style="border:none; border-top: 2px dashed var(--border); margin: 28px 0;">

  <div>
    <h3 style="font-size: 16px; color: var(--secondary); margin-bottom: 12px; display:flex; align-items:center; gap:8px;">
      <span>🚀 【Part B】外部サービス・クラウドAPI連携マップ（システム境界線）</span>
    </h3>
    <p style="font-size: 13px; color: var(--text-sub); margin-bottom: 12px;">
      インターネットを越えて通信する中核クラウドAPIおよびブラウザ標準機能の一覧です。
    </p>

    <table class="clean-table">
      <thead>
        <tr>
          <th>連携先サービス・API</th>
          <th>分類・認証方式</th>
          <th>送受信データ ＆ 連携目的</th>
          <th>通信障害・停止時の影響</th>
        </tr>
      </thead>
      <tbody><!-- 中核API詳細行 --></tbody>
    </table>
  </div>
</div>

<!-- TAB_3 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 3 : Processing Flow</span>
    <h2 class="card-title">🗺️ 第3章：主要機能の処理フロー（操作とシステム動作の流れ）</h2>
    <p class="card-desc">ユーザー操作から完了までのバトンリレーです。内部処理と外部通信の境目を明示しています。</p>
  </div>
  <div class="journey-container">
    <div class="journey-step">
      <div class="step-badge">1</div>
      <div class="step-main">
        <div class="step-title">
          <span>（ステップ名）</span>
          <span class="step-actor">（実行担当：ユーザー/ローカルJS/Gemini API等）</span>
        </div>
        <p class="step-desc">（処理内容の通訳解説）</p>
      </div>
    </div>
    <!-- 4〜5ステップ作成 -->
  </div>
</div>
================================================================================
"""
    raw_html_1, _ = call_gemini_api(api_key, prompt_1, sys_instruction_1)

    # フェーズ1の完全性検証（TAB_1〜3）
    for ch in [1, 2, 3]:
        if f"<!-- TAB_{ch} -->" not in raw_html_1:
            raise RuntimeError(f"【生成打ち切り検知】第{ch}章の出力が途中で途切れました。不完全なHTMLの保存を中止しました。もう一度「一撃生成」ボタンを押して再生成してください。")

    # ==========================
    # フェーズ2：解剖・監査執筆（第4章〜第6章）
    # ==========================
    sys_instruction_2 = (
        "あなたは世界最高峰のソフトウェア品質保証責任者兼『初心者のための翻訳者』です。"
        "第4章〜第6章を執筆してください。"
        f"{self_eval_guidance}\n"
        f"{changelog_status_prompt}"
        "【第5章・第6章の絶対判定ルール（違反厳禁）】\n"
        "1. 判定ステータスは以下の3つの語彙のみを使用し、完全一致で出力すること（表記揺れ絶対禁止）：\n"
        "   - '<span class=\"badge success\">🟢 適合</span>'\n"
        "   - '<span class=\"badge warning test-badge-interactive\" onclick=\"toggleTestBadge(this)\">🟡 要確認</span>'\n"
        "   - '<span class=\"badge danger test-badge-interactive\" onclick=\"toggleTestBadge(this)\">🔴 不適合</span>'\n"
        "   ※「合格」「Pass」「要警戒」「注意」「◯ △ ×」「未実施」などの表現は絶対に使用しないこと。\n"
        "2. 【親切な評価と客観的メリハリの原則】\n"
        "   - 静的コード解析で該当関数・実装が確実に確認できる論理項目は『🟢 適合』とする。\n"
        "   - マイク認識、スピーカー発声、ブラウザ環境、通信遅延、バッチ起動など、**『コード上は対策ロジック（関数名等）が実装済みだが、外部環境や物理ハードウェアに依存するため実機検証が必要な項目』は必ず『🟡 要確認』**とし、検証基準や根拠に『※コード上は〇〇関数等で実装済みだが、実機環境での動作テストが必要』と親切に明記すること！\n"
        "   - 未実装やデータ消失などの重大リスク・欠陥がある項目は必ず『🔴 不適合』とする。\n"
        "3. 第6章の『⚠️ 要確認項目の検証アクションガイド』には、判定が『🟡 要確認』となった項目について、人間が実機で手動テストするための具体的アクション手順を必ず1対1で記述すること。"
    )

    prompt_2 = f"""
以下のシステム情報に基づき、第4章〜第6章を執筆してください。
{common_context}
================================================================================
必ず以下のタグ形式で順番に出力してください。余計な解説は不要です。

<!-- TAB_4 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 4 : Anatomy & Code Link</span>
    <h2 class="card-title">🧩 第4章：体内構造 ⇔ コード完全リンク対照表</h2>
    <p class="card-desc">身体の器官の役割と、それをコード上で具体的に担っているファイル・関数を1対1で紐解いた体内解剖マップです。</p>
  </div>
  <h3>器官比喩 ⇔ ソースマップ対照表（1対1完全リンク）</h3>
  <table class="clean-table">
    <thead>
      <tr>
        <th style="width: 18%;">身体の器官比喩</th>
        <th style="width: 32%;">体内での具体的な役割・働き</th>
        <th style="width: 35%;">実際にその機能を担うファイル ＆ 関数（具体的動作）</th>
        <th style="width: 15%;">もし麻痺したら？</th>
      </tr>
    </thead>
    <tbody><!-- 1対1完全リンク行 --></tbody>
  </table>
  <div class="box box-primary" style="margin-top:20px;">
    <h3>将来のファイル分割提言（To-Be構成）</h3>
    <ul><!-- 推奨分割案 --></ul>
  </div>
</div>

<!-- TAB_5 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 5 : Deep Diagnosis & Traps</span>
    <h2 class="card-title">🩺 第5章：現場の罠 ＆ 7大地雷リスクの実コード健康診断</h2>
    <p class="card-desc">現場で起きたトラブルと、生成AI協働開発特有の落とし穴に対する安全監査です。</p>
  </div>
  <div class="box box-danger">
    <h3>🚨 現場で起きた重大トラブル・教訓の解説</h3>
    <p>（AIへのアバウト指示や最新API仕様タイムラグによる事故、データ消失の教訓を平易に解説）</p>
  </div>

  <div class="eval-standard-box">
    <div class="eval-standard-row">
      <span class="eval-standard-title">⚖️ 判定基準：</span>
      <span class="eval-standard-item"><strong style="color:var(--success);">🟢 適合</strong>（コード上で安全設計を確認済）</span>
      <span class="eval-standard-item"><strong style="color:var(--warn);">🟡 要確認</strong>（コード対策済だが実機環境での動作検証が必要）</span>
      <span class="eval-standard-item"><strong style="color:var(--danger);">🔴 不適合</strong>（未実装または重大な地雷リスクあり）</span>
    </div>
    <div class="eval-standard-note">
      💡 <strong>開発者への親切注記：</strong> コード内に防衛関数が組まれていても、マイク・音声・通信等の外部境界は端末やOS環境に左右されるため、品質保証（QA）基準として『🟡 要確認』として明示しています。
    </div>
  </div>

  <h3>🩺 代表的な7大地雷リスクの実コード健康診断</h3>
  <table class="clean-table">
    <thead><tr><th>地雷項目</th><th>AIやらかし傾向</th><th>診断判定</th><th>コード根拠</th></tr></thead>
    <tbody><!-- 7行（判定列は「🟢 適合」「🟡 要確認」「🔴 不適合」のいずれかのみ） --></tbody>
  </table>

  <div class="box box-warning" style="margin-top: 18px;">
    <h3>⚠️ 要確認項目の検証アクションガイド</h3>
    <ul><!-- 実機確認手順 --></ul>
  </div>
</div>

<!-- TAB_6 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 6 : Operational Rules & Audit</span>
    <h2 class="card-title">📋 第6章：日常運用ルール ＆ 客観的テスト判定</h2>
    <p class="card-desc">システムの日常運用方針と、実機検証に基づく品質保証チェックリストです。</p>
  </div>
  <div class="box box-secondary">
    <h3>📌 日常運用の心得 ＆ 禁忌（NG）操作</h3>
    <ul>
      <li><strong>安定運用の勘所：</strong> （解説）</li>
      <li><strong>絶対禁止（トラウマ回避）：</strong> （解説）</li>
    </ul>
  </div>

  <div class="eval-standard-box">
    <div class="eval-standard-row">
      <span class="eval-standard-title">⚖️ 判定基準：</span>
      <span class="eval-standard-item"><strong style="color:var(--success);">🟢 適合</strong>（静的解析により仕様担保を確認）</span>
      <span class="eval-standard-item"><strong style="color:var(--warn);">🟡 要確認</strong>（コード実装済・実機手動テスト推奨 / クリックで適合へ切替可）</span>
      <span class="eval-standard-item"><strong style="color:var(--danger);">🔴 不適合</strong>（テスト不合格または機能不全）</span>
    </div>
    <div class="eval-standard-note">
      💡 <strong>判定の考え方：</strong> 静的コード解析で担保できるロジックは『🟢 適合』、スピーカー・マイク・ブラウザ権限・ネットワーク等の実機検証が必要な動的テストは『🟡 要確認』とし、下記の検証ガイドに具体的な手順を紐付けています。
    </div>
  </div>

  <h3 style="margin-top:14px;">★ 正常動作テストチェックリスト（10項目完走）</h3>
  <table class="clean-table">
    <thead><tr><th>No</th><th>テスト項目</th><th>検証基準（コード担保状況と実機確認点）</th><th>判定</th></tr></thead>
    <tbody><!-- 1〜10項目（動的項目はコード実装状況を明記した上で「🟡 要確認」とする） --></tbody>
  </table>

  <div class="box box-warning" style="margin-top: 18px;">
    <h3>⚠️ 要確認項目の検証アクションガイド</h3>
    <ul><!-- 判定が「🟡 要確認」となった項目に対する、具体的な実機テスト手順を明記 --></ul>
  </div>
</div>
================================================================================
"""
    raw_html_2, _ = call_gemini_api(api_key, prompt_2, sys_instruction_2)

    # フェーズ2の完全性検証（TAB_4〜6）
    for ch in [4, 5, 6]:
        if f"<!-- TAB_{ch} -->" not in raw_html_2:
            raise RuntimeError(f"【生成打ち切り検知】第{ch}章の出力が途中で途切れました。不完全なHTMLの保存を中止しました。もう一度「一撃生成」ボタンを押して再生成してください。")

    # ==========================
    # フェーズ3：手順執筆（第7章〜第8章）
    # ==========================
    sys_instruction_3 = (
        "あなたは世界最高峰のテクニカルライター兼『初心者のための翻訳者』です。"
        "第7章（AI操縦マニュアル）および第8章（簡易操作マニュアル）を執筆してください。"
        f"{self_eval_guidance}\n"
        "【第8章執筆の重要ルール】\n"
        "1. 日常運用のための平易な手順書としてStep 1〜5を漏れなく記述すること。\n"
        "2. Step 4には『黒い画面（コマンドプロンプト）を「×」または Ctrl+C で必ず終了すること（二重起動によるポート衝突防止）』および『履歴を初期化したい場合は spec_studio_snapshot.json を削除して再実行すればいつでもRev.1から再スタート可能』であることを明記すること。"
    )

    prompt_3 = f"""
以下のシステム情報に基づき、第7章および第8章を執筆してください。
{common_context}
================================================================================
必ず以下のタグ形式で順番に出力してください。余計な解説は不要です。

<!-- TAB_7 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 7 : AI Direction Manual</span>
    <h2 class="card-title">🎓 第7章：生成AI操縦マニュアル（天国と地雷）</h2>
    <p class="card-desc">初心者がAIにアバウトな指示を出して自滅しないための、具体的指示の処方箋です。</p>
  </div>
  <div class="box box-warning">
    <h3>☀️ 推奨プロンプト（Good）vs 💀 失敗プロンプト（Bad）の実例比較</h3>
    <p>...</p>
  </div>
  <h3>🤖 AI Studio用お約束カンペ（コピー＆ペースト用）</h3>
  <div class="prompt-box" id="ai-prompt-box">
【厳守・AI開発者への絶対指令】
（安全なコピペ指示文）
  </div>
</div>

<!-- TAB_8 -->
<div class="card">
  <div class="card-header">
    <span class="card-tag">Chapter 8 : Quick User Manual</span>
    <h2 class="card-title">📖 第8章：簡易操作マニュアル（簡易手順書）</h2>
    <p class="card-desc">初心者がシステムを意図通りに動かすための平易な手順書です。</p>
  </div>
  
  <div class="box box-primary">
    <h3>🚀 Step 1：起動の準備（日常運用）</h3>
    <p>※本手順は開発環境の構築用ではなく、日常のシステム起動を前提としています。</p>
    <p>（起動バッチがある場合は『〇〇.batをダブルクリック』と明記）</p>
  </div>

  <div class="box box-secondary">
    <h3>🖥️ Step 2：画面の基本構成</h3>
    <p>（画面の主要構成を平易に解説）</p>
  </div>

  <div class="box">
    <h3>🎯 Step 3：基本操作のながれ（標準シナリオ）</h3>
    <ol>
      <li><strong>手順1：</strong> （画面を開いて何を入力・選択するか）</li>
      <li><strong>手順2：</strong> （どのボタンを押すか）</li>
      <li><strong>手順3：</strong> （実行後に何が表示されれば成功か）</li>
    </ol>
  </div>

  <div class="box">
    <h3>⚙️ Step 4：データの保存と安全な終了手順</h3>
    <p>
      作業完了後の保存方法とともに、<strong>『ブラウザを閉じるだけでなく、裏で動いている黒い画面（コマンドプロンプト）を「×」で閉じるか、Ctrl+C で必ず終了すること（二重起動によるポート衝突防止）』</strong>を強調して明記。<br>
      また、<strong>『履歴を初期化してRev.1から再スタートしたい場合は、手動で spec_studio_snapshot.json を削除して実行すればいつでも安全にリセット可能』</strong>である旨も記載。
    </p>
  </div>

  <div class="box box-warning">
    <h3>🔧 Step 5：困ったときの対処法（簡単リカバリー）</h3>
    <p>（動かなくなったときのリカバリー手順）</p>
  </div>
</div>
================================================================================
"""
    raw_html_3, _ = call_gemini_api(api_key, prompt_3, sys_instruction_3)

    # フェーズ3の完全性検証（TAB_7〜8）
    for ch in [7, 8]:
        if f"<!-- TAB_{ch} -->" not in raw_html_3:
            raise RuntimeError(f"【生成打ち切り検知】第{ch}章の出力が途中で途切れました。不完全なHTMLの保存を中止しました。もう一度「一撃生成」ボタンを押して再生成してください。")

    raw_html = raw_html_1 + "\n" + raw_html_2 + "\n" + raw_html_3

    # 全8章の完全性総合監査
    for ch in range(1, 9):
        if f"<!-- TAB_{ch} -->" not in raw_html:
            raise RuntimeError(f"【整合性監査エラー】第{ch}章のブロックがダッシュボード内に存在しません。再生成をお試しください。")

    theme = {
        "theme_name": "思考実現サファイア・インテリジェント",
        "symbol_icon": "🚀",
        "sub_icon": "🧭",
        "primary_color": "#0ea5e9",
        "primary_dark": "#0369a1",
        "primary_light": "#e0f2fe",
        "secondary_color": "#6366f1",
        "bg_main": "#f8fafc",
        "bg_card": "#ffffff",
        "text_main": "#0f172a",
        "text_sub": "#475569",
        "border_color": "#e2e8f0"
    }

    meta_match = re.search(r"<!-- DESIGN_META -->\s*(\{[\s\S]*?\})", raw_html)
    if meta_match:
        try:
            parsed = json.loads(meta_match.group(1))
            if isinstance(parsed, dict):
                theme.update(parsed)
        except Exception as e:
            print(f"メタデータ解析警告: {e}")

    gallery_html = ""
    if scan_data["image_assets"]:
        chips = []
        for img in scan_data["image_assets"]:
            safe_name = html.escape(img['name'])
            chips.append(f"""
            <div class="asset-chip">
              <img src="{safe_name}" class="asset-chip-thumb" alt="{safe_name}" title="ホバー拡大 / {safe_name}" onerror="this.style.display='none'">
              <span>{safe_name}</span>
              <span class="asset-chip-meta">({img['size_kb']}KB)</span>
            </div>
            """)
        gallery_html = f"""
        <div style="margin-top: 14px; margin-bottom: 14px;">
          <h4 style="font-size: 13.5px; font-weight: 800; color: var(--text-main); margin-bottom: 6px;">🎨 登録画像アセット（ホバーで拡大プレビュー）</h4>
          <div class="asset-chips-container">
            {''.join(chips)}
          </div>
        </div>
        """
    else:
        gallery_html = """
        <div class="box box-secondary" style="margin: 16px 0; border-style: dashed;">
          <h4 style="font-size: 13.5px; font-weight: 800;">📦 画像アセット構成</h4>
          <p style="font-size: 13px;">画像アセットファイルは検出されませんでした（プログラム単体（ロジック完結）で自律動作しています）。</p>
        </div>
        """

    def extract_tab(num):
        pattern = rf"<!-- TAB_{num} -->([\s\S]*?)(?=<!-- TAB_\d -->|$)"
        match = re.search(pattern, raw_html)
        if match:
            content = match.group(1).strip()
            if num == 2:
                if "<!-- ASSET_PLACEHOLDER -->" in content:
                    content = content.replace("<!-- ASSET_PLACEHOLDER -->", gallery_html)
                else:
                    content += gallery_html
            return content
        return f"<div class='card'><p>第{num}章の生成データを解析できませんでした。</p></div>"

    history_cards = []
    raw_history_list = diff_info.get("history", [])
    history_list = [sanitize_history_record(rec) for rec in raw_history_list]

    if not history_list:
        api_text = f"（中核連携: {', '.join(scan_data['core_apis'])}) " if scan_data['core_apis'] else "（内部完結型）"
        history_list = [{
            "rev": diff_info.get("rev", 1),
            "version": scan_data["version"],
            "date": diff_info.get("created_at", ""),
            "summary": f"初回ベースライン設計書・品質ダッシュボード確立 (Ver {scan_data['version']})",
            "purpose": f"「{scan_data['project_name']}」の全体構造可視化および初期設計ベースラインの確立 {api_text}",
            "improvements": "新規プロジェクトとしてのファイル体系、責務構造、運用ガイドラインの初版策定",
            "added_files": [f["name"] for f in scan_data["files"]],
            "modified_files": [],
            "removed_files": [],
            "net_lines": f"+{scan_data['total_lines']}"
        }]

    for idx, h in enumerate(reversed(history_list)):
        is_latest = (idx == 0)
        open_attr = "open" if is_latest else ""
        rev_class = "is-latest-rev" if is_latest else "is-past-rev"

        rev_no = h.get("rev", 1)
        ver_str = html.escape(str(h.get("version", "1.0.0")))
        date_str = html.escape(str(h.get("date", "")))
        summary_str = html.escape(str(h.get("summary", "")))
        purpose_str = html.escape(str(h.get("purpose", summary_str)))
        improvements_str = html.escape(str(h.get("improvements", "コードベースの安定化")))
        net_lines = html.escape(str(h.get("net_lines", "+0")))

        added = h.get("added_files", [])
        modified = h.get("modified_files", [])
        removed = h.get("removed_files", [])

        diff_chips = []
        for a in added:
            diff_chips.append(f'<span class="diff-chip" style="color:var(--success);">🟢 新設: {html.escape(a)}</span>')
        for m in modified:
            diff_chips.append(f'<span class="diff-chip" style="color:var(--warn);">🟡 更新: {html.escape(m)}</span>')
        for r in removed:
            diff_chips.append(f'<span class="diff-chip" style="color:var(--danger);">🔴 削除: {html.escape(r)}</span>')
        
        diff_chips_html = "".join(diff_chips) if diff_chips else '<span style="color:var(--text-sub);">物理ファイルの追加・削除・行数変更なし（コード微調整）</span>'

        card_html = f"""
        <details class="changelog-card {rev_class}" {open_attr}>
          <summary class="changelog-summary">
            <div class="changelog-rev">
              <span>Rev.{rev_no} (Ver {ver_str})</span>
              <span style="font-size: 12.5px; font-weight: normal; color: var(--text-sub);">[{date_str}]</span>
            </div>
            <div class="changelog-badges">
              <span class="badge success">{net_lines} 行</span>
              <span class="badge warning">{summary_str[:38]}...</span>
            </div>
          </summary>
          <div class="changelog-detail">
            <div class="changelog-row">
              <span class="changelog-label">🎯 改修目的・方針：</span>
              <span class="changelog-val">{purpose_str}</span>
            </div>
            <div class="changelog-row">
              <span class="changelog-label">✨ 前回課題の是正効果：</span>
              <span class="changelog-val" style="color: var(--success); font-weight: 600;">{improvements_str}</span>
            </div>
            <div class="changelog-row">
              <span class="changelog-label">🛠️ 物理差分の詳細：</span>
              <div class="changelog-val diff-chips-container">{diff_chips_html}</div>
            </div>
          </div>
        </details>
        """
        history_cards.append(card_html)

    latest_summary_display = diff_info.get("latest_rev_summary", "初回ベースライン確立")
    latest_net_display = diff_info.get("latest_rev_net", "+0")

    changelog_tab_html = f"""
    <div class="card">
      <div class="card-header">
        <span class="card-tag">Changelog & Audit History</span>
        <h2 class="card-title">📜 プログラム版数 ＆ 改修・監査履歴</h2>
        <p class="card-desc">プログラムの確定改修履歴と、設計書の版数変遷の記録です（印刷時は最新Revのみフル展開）。</p>
      </div>

      <div class="compact-metric-bar">
        <div class="metric-item">
          <strong>最新版：</strong>
          <span class="badge success">Rev.{diff_info['rev']} (Ver {html.escape(str(scan_data['version']))})</span>
        </div>
        <div class="metric-item">
          <strong>監査日時：</strong>
          <span style="color: var(--text-sub);">{html.escape(diff_info['created_at'])}</span>
        </div>
        <div class="metric-item" style="margin-left: auto;">
          <strong>Rev.{diff_info['rev']} 改修実績：</strong>
          <span style="color: var(--text-main); font-weight: 700;">{html.escape(latest_summary_display)} ({html.escape(latest_net_display)}行)</span>
        </div>
      </div>

      <h3 style="margin-bottom: 12px; font-size: 15px;">📚 版数変遷タイムライン（最新Rev展開中）</h3>
      {''.join(history_cards)}
    </div>
    """

    total_assets = len(scan_data["image_assets"]) + len(scan_data["audio_assets"])

    final_html = (
        DASHBOARD_TEMPLATE
        .replace("{{PROJECT_TITLE}}", html.escape(scan_data["project_name"]))
        .replace("{{PROJECT_VERSION}}", html.escape(str(scan_data["version"])))
        .replace("{{THEME_SYMBOL}}", theme.get("symbol_icon", "🚀"))
        .replace("{{THEME_SUB_SYMBOL}}", theme.get("sub_icon", "🧭"))
        .replace("{{THEME_NAME}}", html.escape(theme.get("theme_name", "思考実現サファイア")))
        .replace("{{REV_NUMBER}}", str(diff_info["rev"]))
        .replace("{{TOTAL_FILES}}", str(scan_data["total_files"]))
        .replace("{{TOTAL_LINES}}", f"{scan_data['total_lines']:,}")
        .replace("{{TOTAL_ASSETS}}", str(total_assets))
        .replace("{{THEME_PRIMARY}}", theme.get("primary_color", "#0ea5e9"))
        .replace("{{THEME_PRIMARY_DARK}}", theme.get("primary_dark", "#0369a1"))
        .replace("{{THEME_PRIMARY_LIGHT}}", theme.get("primary_light", "#e0f2fe"))
        .replace("{{THEME_SECONDARY}}", theme.get("secondary_color", "#6366f1"))
        .replace("{{THEME_BG_MAIN}}", theme.get("bg_main", "#f8fafc"))
        .replace("{{THEME_BG_CARD}}", theme.get("bg_card", "#ffffff"))
        .replace("{{THEME_TEXT_MAIN}}", theme.get("text_main", "#0f172a"))
        .replace("{{THEME_TEXT_SUB}}", theme.get("text_sub", "#475569"))
        .replace("{{THEME_BORDER}}", theme.get("border_color", "#e2e8f0"))
        .replace("{{CHANGELOG_TAB}}", changelog_tab_html)
        .replace("{{CONTENT_TAB_1}}", extract_tab(1))
        .replace("{{CONTENT_TAB_2}}", extract_tab(2))
        .replace("{{CONTENT_TAB_3}}", extract_tab(3))
        .replace("{{CONTENT_TAB_4}}", extract_tab(4))
        .replace("{{CONTENT_TAB_5}}", extract_tab(5))
        .replace("{{CONTENT_TAB_6}}", extract_tab(6))
        .replace("{{CONTENT_TAB_7}}", extract_tab(7))
        .replace("{{CONTENT_TAB_8}}", extract_tab(8))
    )

    return final_html

# ==============================================================================
# 8. メイン実行部（Threading Server ＆ 127.0.0.1 安全バインド）
# ==============================================================================
class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

def main():
    print("=" * 68)
    print(f"  ✨ SpecStudio v{__version__} - 初心者 × 生成AI 協働開発コンパス")
    print(f"  対象プロジェクト: {FALLBACK_PROJECT_NAME}")
    print("=" * 68)
    print(f"  対象ディレクトリ: {BASE_DIR}")
    if VERSION_FILE.exists():
        print(f"  版数構成ファイル: {VERSION_FILE.name} (連動中: Ver {__version__})")
    else:
        print(f"  版数構成ファイル: 未検出 (メモリ安全モード: Ver {__version__})")
    print(f"  AI推論モデル: 主軸 [{PRIMARY_MODEL}] ＆ 控 [{BACKUP_MODEL}]")

    server_port = DEFAULT_PORT
    httpd = None

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(DEFAULT_PORT, DEFAULT_PORT + 20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), StudioRequestHandler)
            server_port = port
            break
        except OSError:
            continue

    if not httpd:
        print("\n【エラー】空いているローカルポートが見つかりませんでした。")
        sys.exit(1)

    url = f"http://127.0.0.1:{server_port}"
    print(f"  ローカルサーバーを起動しました: {url} (127.0.0.1限定)")
    print("  ブラウザを自動起動します...")
    print("  (終了するときは、このウィンドウを閉じるか Ctrl+C を押してください)")
    print("=" * 68)

    try:
        webbrowser.open(url)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nシステムを安全に終了しました。")
    except Exception as e:
        print(f"\n【実行時エラー】: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()