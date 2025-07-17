# LizaAlert Detector Bot 🤖🆘

YOLOv11n-based Telegram-бот, который отмечает людей на аэрофотоснимках.  
Модель крутится в Hugging Face Spaces (CPU), бот — на Railway (бесплатный план).

---

## 🗺️ Архитектура

```mermaid
flowchart LR
    subgraph Railway
        A[Telegram Bot<br>long-polling] -->|POST image| B[(HF Space /predict)]
        B -->|annotated jpg| A
        C[(Flask /)] -. health .-> U[Railway LB]
    end
    subgraph HF Spaces
        B
    end