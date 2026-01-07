import asyncio
import aiohttp
import json


async def test_api():
    BASE = "http://localhost:8080"
    
    async with aiohttp.ClientSession() as session:
        print("🚀 Запуск теста REST API для объявлений (aiohttp)")
        print("="*60)
        
        # Сначала регистрируем и логинимся
        print("\n0. 🔐 РЕГИСТРАЦИЯ И АУТЕНТИФИКАЦИЯ:")
        
        # Регистрация
        async with session.post(
            f"{BASE}/register",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        ) as resp:
            data = await resp.json() if resp.status == 200 else await resp.text()
            print(f"POST /register -> {resp.status}: {data}")
        
        # Логин для получения токена
        async with session.post(
            f"{BASE}/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                token = data.get('token')
                print(f"POST /login -> {resp.status}: Token получен")
            else:
                print(f"POST /login -> {resp.status}: {await resp.text()}")
                return
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Создание объявлений
        print("\n1. 📝 СОЗДАНИЕ ОБЪЯВЛЕНИЙ:")
        for i in range(3):
            async with session.post(
                f"{BASE}/advertisements",
                json={
                    "title": f"Продам товар {i+1}",
                    "description": f"Отличное состояние, новый"
                },
                headers=headers
            ) as resp:
                data = await resp.json() if resp.status == 201 else await resp.text()
                emoji = "🟢" if resp.status == 201 else "🔴"
                print(f"{emoji} POST /advertisements -> {resp.status}: {data}")
        
        # 2. Получение всех объявлений
        print("\n2. 📋 ВСЕ ОБЪЯВЛЕНИЯ:")
        async with session.get(f"{BASE}/advertisements") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"🟢 GET /advertisements -> {resp.status}: Всего {data['total']} объявлений")
                for i, ad in enumerate(data['advertisements'], 1):
                    print(f"   {i}. [{ad['id']}] {ad['title']} - user_id: {ad['user_id']}")
            else:
                print(f"🔴 GET /advertisements -> {resp.status}: {await resp.text()}")
        
        # 3. Поиск
        print("\n3. 🔍 ПОИСК:")
        async with session.get(f"{BASE}/advertisements/search?q=товар") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"🟢 GET /advertisements/search?q=товар -> {resp.status}: Найдено {data['count']}")
            else:
                print(f"🔴 GET /advertisements/search?q=товар -> {resp.status}: {await resp.text()}")
        
        # 4. Удаление
        print("\n4. 🗑️ УДАЛЕНИЕ:")
        async with session.get(f"{BASE}/advertisements") as resp:
            if resp.status == 200:
                data = await resp.json()
                if data['advertisements']:
                    ad_id = data['advertisements'][0]['id']
                    async with session.delete(
                        f"{BASE}/advertisements/{ad_id}",
                        headers=headers
                    ) as del_resp:
                        if del_resp.status == 204:
                            print(f"🟢 DELETE /advertisements/{ad_id} -> {del_resp.status}: No Content")
                        else:
                            data = await del_resp.text()
                            print(f"🔴 DELETE /advertisements/{ad_id} -> {del_resp.status}: {data}")
        
        # 5. Финальная проверка
        print("\n5. 📊 ИТОГОВАЯ СТАТИСТИКА:")
        async with session.get(f"{BASE}/advertisements") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"   В базе осталось: {data['total']} объявлений")
                print(f"   Пагинация: страница {data['page']} из {data['pages']}")
                print(f"   Размер страницы: {data['per_page']}")
        
        print("\n" + "="*60)
        print("✅ Асинхронное тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(test_api())