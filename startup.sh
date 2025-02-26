#!/bin/bash
# 使用 --no-dependencies 安裝 google-genai 的啟動腳本
set -e  # Exit immediately if a command exits with a non-zero status

echo "===== 開始部署 STT 專案 (忽略依賴衝突版本) ====="

# 安裝 git if needed
echo "===== 檢查並安裝 git ====="
if ! command -v git &> /dev/null; then
    echo "Git 未找到。安裝 git..."
    sudo apt-get update
    sudo apt-get install -y git
else
    echo "Git 已安裝。"
fi

# 下載並安裝 Miniconda if needed
echo "===== 檢查 Miniconda 安裝 ====="
if [ -d "$HOME/miniconda" ]; then
    echo "Miniconda 已安裝。跳過安裝。"
else
    echo "===== 下載並安裝 Miniconda ====="
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
    bash ~/miniconda.sh -b -p $HOME/miniconda
    rm ~/miniconda.sh
    
    # 初始化 conda for bash
    echo "===== 初始化 conda ====="
    source $HOME/miniconda/bin/activate
    conda init bash
    
    # 立即套用變更
    source ~/.bashrc
fi

# 確保 conda 命令可用
export PATH="$HOME/miniconda/bin:$PATH"
source $HOME/miniconda/bin/activate

# 創建並啟用 conda 環境
echo "===== 檢查 conda 環境 gemini-stt ====="
if conda info --envs | grep -q "gemini-stt"; then
    echo "Conda 環境 gemini-stt 已存在。跳過創建。"
else
    echo "===== 創建 conda 環境 gemini-stt with Python 3.11 ====="
    conda create -y -n gemini-stt python=3.11
fi

# 啟用環境
echo "===== 啟用 conda 環境 gemini-stt ====="
conda activate gemini-stt

# 克隆儲存庫
echo "===== 檢查儲存庫 ====="
if [ -d "python_stt_micro_batch" ]; then
    echo "儲存庫已克隆。檢查更新。"
    cd python_stt_micro_batch
    
    # 檢查是否有更新
    echo "檢查儲存庫更新..."
    git fetch
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u})
    
    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "有可用更新。拉取最新變更..."
        git pull
    else
        echo "儲存庫是最新的。"
    fi
else
    # 克隆儲存庫
    echo "===== 克隆儲存庫 ====="
    git clone https://github.com/lujames13/python_stt_micro_batch.git
    cd python_stt_micro_batch
fi

# 從 GCP 元數據設置環境變數
echo "===== 從 GCP 元數據設置環境變數 ====="
PROJECT_ID=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")
echo "檢測到的 PROJECT_ID: $PROJECT_ID"
ZONE=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/zone" -H "Metadata-Flavor: Google")
LOCATION=$(echo $ZONE | sed 's/.*\/\([^/]*\)-[^/]*$/\1/')
echo "檢測到的 LOCATION (region): $LOCATION"
export PROJECT_ID=$PROJECT_ID
export LOCATION=$LOCATION
echo "export PROJECT_ID=$PROJECT_ID" >> ~/.bashrc
echo "export LOCATION=$LOCATION" >> ~/.bashrc

# 解決依賴衝突
echo "===== 解決依賴衝突 ====="
# 備份原始 requirements.txt
cp requirements.txt requirements.txt.bak

# 修改 requirements.txt 移除 google-genai
echo "修改 requirements.txt 移除 google-genai..."
grep -v "google-genai" requirements.txt > requirements-temp.txt
mv requirements-temp.txt requirements.txt

# 安裝除 google-genai 外的所有依賴
echo "安裝除 google-genai 外的所有依賴..."
pip install -r requirements.txt

# 使用 --no-dependencies 安裝 google-genai
echo "使用 --no-dependencies 安裝 google-genai..."
pip install --no-dependencies google-genai

# 檢查安裝的版本
echo "安裝的套件版本:"
pip list | grep -E 'gradio|websockets|google-genai'

# 生成 protocol buffers
echo "===== 檢查並生成 protocol buffers ====="
if [ -f "proto/stt_pb2.py" ] && [ -f "proto/stt_pb2_grpc.py" ]; then
    echo "Protocol buffers 已生成。跳過生成。"
else
    echo "生成 protocol buffers..."
    cd proto
    bash generate_pb.sh
    cd ..
fi

# 記錄當前目錄
CURRENT_DIR=$(pwd)

# 引導使用者進行身份驗證和手動啟動 gradio_test
echo ""
echo "===== 部署完成 ====="
echo ""
echo "接下來，請完成以下步驟:"
echo ""
echo "1. 執行 Google Cloud 身份驗證:"
echo "   gcloud auth application-default login"
echo ""
echo "2. 啟動 Gradio 測試界面 (已自動設定正確目錄):"
echo "   conda activate gemini-stt && cd $CURRENT_DIR && python3 gradio-test.py -l cmn-Hant-TW -project $PROJECT_ID -location $LOCATION"
echo ""
