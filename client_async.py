import asyncio
import aiohttp
import json


async def test_api():
    BASE = "http://localhost:8080"
    
    async with aiohttp.ClientSession() as session:
        print("🚀 Запуск теста REST API для объявлений (aiohttp)")
        print("="*60)
        
        # 1. Создание объявлений
        print("\n1. 📝 СОЗДАНИЕ ОБЪЯВЛЕНИЙ:")
        for i in range(3):
            async with session.post(
                f"{BASE}/advertisements",
                json={
                    "title": f"Продам товар {i+1}",
                    "description": f"Отличное состояние, новый",
                    "owner": f"Продавец {i+1}"
                }
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
                    print(f"   {i}. [{ad['id']}] {ad['title']} - {ad['owner']}")
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
        # Сначала получим ID первого объявления
        async with session.get(f"{BASE}/advertisements") as resp:
            if resp.status == 200:
                data = await resp.json()
                if data['advertisements']:
                    ad_id = data['advertisements'][0]['id']
                    async with session.delete(f"{BASE}/advertisements/{ad_id}") as del_resp:
                        data = await del_resp.json() if del_resp.status == 200 else await del_resp.text()
                        emoji = "🟢" if del_resp.status == 200 else "🔴"
                        print(f"{emoji} DELETE /advertisements/{ad_id} -> {del_resp.status}: {data}")
        
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


async def test_html_responses():
    """Тестирование HTML ответов"""
    BASE = "http://localhost:8080"
    
    print("\n🌐 Тестирование HTML ответов:")
    print("-" * 40)
    
    async with aiohttp.ClientSession() as session:
        # Главная страница
        async with session.get(BASE, headers={'Accept': 'text/html'}) as resp:
            if resp.status == 200:
                print("🟢 Главная страница (HTML) работает")
        
        # Список объявлений в HTML
        async with session.get(
            f"{BASE}/advertisements", 
            headers={'Accept': 'text/html'}
        ) as resp:
            if resp.status == 200:
                print("🟢 Список объявлений (HTML) работает")
        
        # Поиск в HTML
        async with session.get(
            f"{BASE}/advertisements/search?q=товар",
            headers={'Accept': 'text/html'}
        ) as resp:
            if resp.status == 200:
                print("🟢 Поиск объявлений (HTML) работает")


if __name__ == "__main__":
    # Запускаем оба теста
    asyncio.run(test_api())
    # asyncio.run(test_html_responses())  # Раскомментируй для теста HTML