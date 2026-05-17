# Multiple Gmail Account Storage

A secure, isolated browser launcher for managing multiple Gmail/Google accounts using [Camoufox](https://camoufox.com/python). 
Designed to bypass strict fingerprinting, prevent cross-contamination between accounts, and ensure privacy.

## ✨ Key Features
- **Full Isolation:** Each account (group) runs in a completely separate browser profile (user data dir). Cookies, cache, and sessions will never leak between accounts.
- **Fingerprinting Bypass:** Uses Camoufox configurations to avoid bot/fraud detection from Google's security systems.
- **Resolution Adjustment (Anti-Clipping):** Forces the viewport resolution (1200x700) to match Windows monitor displays, preventing the detection of unnatural screen sizes.
- **Comprehensive Activity Logs:** Tracks all errors, navigations, and technical browser info in real-time to the `logs/` folder (with an automatic filter for sensitive URLs).
- **Path Traversal Security:** Strict input validation when opening profiles, preventing access to folders outside the system (Path Traversal Protection).

## 🚀 How to Use

1. Make sure you have Python installed (version 3.10+ recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run via the **Batch** script (Highly recommended):
   - Double-click on `Open_Group.bat`
   - Enter the group name (Example: `Group_1`, `work_account`, etc.)
   - The Camoufox browser will open and your session will be saved automatically.

*Or via terminal:*
```bash
python run_group.py <group_name>
```

## 📂 Log Structure
Logs are saved in the `/logs` folder with a daily naming format:
`YYYY-MM-DD_<group_name>.log`
The logs will automatically redact sensitive URLs (like `accounts.google.com`) for privacy, while still recording other navigation activities and technical browser info.

## 🛡️ Security Notes
This repository is equipped with a strict `.gitignore`. **NEVER** delete or modify the rules in `.gitignore` to prevent your profile data, *cookies*, and browsing history (the `Group_*` folders) from leaking to the public if you push to an external repository.

## ⚠️ Disclaimer
This tool is created for the legal management of multiple accounts. 
Users are solely responsible for using this tool in accordance with 
the Terms of Service of the platforms being accessed.

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
