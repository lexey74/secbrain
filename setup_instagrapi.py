#!/usr/bin/env python3
"""
Скрипт для создания session.json для Instagrapi
"""
import sys
from instagrapi import Client

def main():
    print("🔐 Создание сессии Instagrapi\n")
    
    username = input("Instagram username: ")
    password = input("Instagram password: ")
    
    try:
        cl = Client()
        print("\n⏳ Авторизация...")
        cl.login(username, password)
        
        # Проверка на 2FA
        if cl.two_factor_required:
            code = input("\n🔢 Введите код из SMS/Email: ")
            cl.login(username, password, verification_code=code)
        
        # Сохранение сессии
        cl.dump_settings("session.json")
        print("\n✅ Сессия сохранена в session.json")
        print("ℹ️  Теперь SecBrain сможет скачивать фото и карусели!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Ошибка авторизации: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
