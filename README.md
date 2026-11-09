# Sherlock Android App 🔍

Python + Kivy দিয়ে তৈরি Sherlock Username Finder Android অ্যাপ।

## Features
- 🔍 সোশ্যাল মিডিয়ায় username search করে
- 📋 ফলাফলের URL কপি করার সুবিধা
- 🌐 ৩০০+ সাইট চেক করে
- 📊 Real-time progress দেখায়

## APK বানাতে

### GitHub Actions দিয়ে (সহজ)
1. এই repo-টি GitHub-এ push করুন
2. **Actions** ট্যাবে যান
3. **Build Sherlock APK** workflow চলতে দিন
4. সম্পন্ন হলে **Artifacts** থেকে APK ডাউনলোড করুন

### লোকালি রান করতে (Termux)
```bash
pip install kivy requests
python main.py
```

## Project Structure
```
sherlock-android/
├── main.py            # Main Kivy app
├── buildozer.spec     # Build configuration
├── .github/workflows/
│   └── build.yml      # GitHub Actions workflow
└── README.md
```
