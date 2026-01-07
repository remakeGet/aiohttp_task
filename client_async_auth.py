import asyncio
import aiohttp
import json


async def test_api_with_auth():
    BASE = "http://localhost:8080"
    
    async with aiohttp.ClientSession() as session:
        print("🚀 Запуск теста с проверкой владельца объявлений")
        print("="*60)
        
        # 1. Регистрация и логин первого пользователя
        print("\n1. 📝 РЕГИСТРАЦИЯ И ЛОГИН (Пользователь 1):")
        
        # Регистрация
        async with session.post(
            f"{BASE}/register",
            json={"email": "user1@example.com", "password": "password123"}
        ) as resp:
            print(f"POST /register -> {resp.status}")
        
        # Логин
        async with session.post(
            f"{BASE}/login",
            json={"email": "user1@example.com", "password": "password123"}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                token1 = data.get('token')
                user1_id = data.get('user_id')
                print(f"✅ User 1: ID={user1_id}, токен получен")
            else:
                print(f"❌ Ошибка входа: {await resp.text()}")
                return
        
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # 2. Создание объявления первым пользователем
        print("\n2. 📝 СОЗДАНИЕ ОБЪЯВЛЕНИЯ (Пользователь 1):")
        async with session.post(
            f"{BASE}/advertisements",
            json={
                "title": "Продам ноутбук Dell",
                "description": "Отличный ноутбук, почти новый"
            },
            headers=headers1
        ) as resp:
            data = await resp.json() if resp.status == 201 else await resp.text()
            print(f"POST /advertisements -> {resp.status}: {data}")
        
        # 3. Регистрация и логин второго пользователя
        print("\n3. 📝 РЕГИСТРАЦИЯ И ЛОГИН (Пользователь 2):")
        
        async with session.post(
            f"{BASE}/register",
            json={"email": "user2@example.com", "password": "password456"}
        ) as resp:
            print(f"POST /register -> {resp.status}")
        
        async with session.post(
            f"{BASE}/login",
            json={"email": "user2@example.com", "password": "password456"}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                token2 = data.get('token')
                user2_id = data.get('user_id')
                print(f"✅ User 2: ID={user2_id}, токен получен")
        
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # 4. Создание объявления вторым пользователем
        print("\n4. 📝 СОЗДАНИЕ ОБЪЯВЛЕНИЯ (Пользователь 2):")
        async with session.post(
            f"{BASE}/advertisements",
            json={
                "title": "Продам iPhone 15",
                "description": "Новый телефон, в коробке"
            },
            headers=headers2
        ) as resp:
            data = await resp.json() if resp.status == 201 else await resp.text()
            print(f"POST /advertisements -> {resp.status}: {data}")
        
        # 5. Получение всех объявлений (без авторизации)
        print("\n5. 📋 ВСЕ ОБЪЯВЛЕНИЯ (публичный доступ):")
        async with session.get(f"{BASE}/advertisements") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"GET /advertisements -> {resp.status}: {data['total']} объявлений")
                for ad in data['advertisements']:
                    print(f"   [{ad['id']}] '{ad['title']}' - user_id: {ad['user_id']}, is_owner: {ad.get('is_owner', False)}")
        
        # 6. Получение всех объявлений от имени User 1
        print("\n6. 📋 ВСЕ ОБЪЯВЛЕНИЯ (с токеном User 1):")
        async with session.get(f"{BASE}/advertisements", headers=headers1) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"GET /advertisements -> {resp.status}:")
                for ad in data['advertisements']:
                    print(f"   [{ad['id']}] '{ad['title']}' - user_id: {ad['user_id']}, is_owner: {ad.get('is_owner', False)}")
        
        # 7. Получение всех объявлений от имени User 2
        print("\n7. 📋 ВСЕ ОБЪЯВЛЕНИЯ (с токеном User 2):")
        async with session.get(f"{BASE}/advertisements", headers=headers2) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"GET /advertisements -> {resp.status}:")
                for ad in data['advertisements']:
                    print(f"   [{ad['id']}] '{ad['title']}' - user_id: {ad['user_id']}, is_owner: {ad.get('is_owner', False)}")
        
        # 8. Проверка конкретного объявления
        print("\n8. 📄 ПРОВЕРКА ОБЪЯВЛЕНИЯ ID=1:")
        print("   Без токена:")
        async with session.get(f"{BASE}/advertisements/1") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"   is_owner: {data.get('is_owner', False)}")
        
        print("   С токеном User 1:")
        async with session.get(f"{BASE}/advertisements/1", headers=headers1) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"   is_owner: {data.get('is_owner', False)}")
        
        print("   С токеном User 2:")
        async with session.get(f"{BASE}/advertisements/1", headers=headers2) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"   is_owner: {data.get('is_owner', False)}")
        
        # 9. Проверка защиты от удаления чужих объявлений
        print("\n9. 🛡️ ПРОВЕРКА ЗАЩИТЫ:")
        print("   User 2 пытается удалить объявление User 1 (ID=1):")
        async with session.delete(f"{BASE}/advertisements/1", headers=headers2) as resp:
            if resp.status == 403:
                print(f"   ✅ DELETE /advertisements/1 -> 403 Forbidden (защита работает!)")
            else:
                print(f"   ❌ DELETE /advertisements/1 -> {resp.status}: {await resp.text()}")
        
        print("   User 1 удаляет свое объявление (ID=1):")
        async with session.delete(f"{BASE}/advertisements/1", headers=headers1) as resp:
            if resp.status == 204:
                print(f"   ✅ DELETE /advertisements/1 -> 204 No Content (успешно)")
            else:
                print(f"   ❌ DELETE /advertisements/1 -> {resp.status}: {await resp.text()}")
        
        print("\n" + "="*60)
        print("✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(test_api_with_auth())