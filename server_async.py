from aiohttp import web
import json
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError

from models_async import Session, Advertisement, init_db, close_db
from schema import validate, CreateAdvertisementRequest, UpdateAdvertisementRequest
from errors import HttpError


@web.middleware
async def error_middleware(request: web.Request, handler):
    """Middleware для обработки ошибок"""
    try:
        response = await handler(request)
        return response
    except HttpError as e:
        return web.json_response(
            {"error": e.message},
            status=e.status_code
        )
    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        return web.json_response(
            {"error": str(e)},
            status=500
        )


@web.middleware
async def session_middleware(request: web.Request, handler):
    """Middleware для управления сессией БД"""
    async with Session() as session:
        request.session = session
        response = await handler(request)
        return response


async def get_advertisement_by_id(session, ad_id: int):
    """Получение объявления по ID"""
    ad = await session.get(Advertisement, ad_id)
    if ad is None:
        raise HttpError(404, "advertisement not found")
    return ad


async def add_advertisement(session, ad: Advertisement):
    """Добавление объявления в БД"""
    session.add(ad)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HttpError(409, "database error")
    except Exception as e:
        await session.rollback()
        raise HttpError(500, str(e))


async def list_advertisements(request: web.Request):
    """Получение всех объявлений с пагинацией и фильтрацией"""
    session = request.session
    
    # Пагинация
    try:
        page = int(request.query.get('page', 1))
        per_page = int(request.query.get('per_page', 10))
    except ValueError:
        raise HttpError(400, "page and per_page must be integers")
    
    # Фильтрация по владельцу
    owner = request.query.get('owner')
    
    # Создаем запрос
    query = select(Advertisement)
    
    if owner:
        query = query.where(Advertisement.owner == owner)
    
    # Сортировка по дате создания (новые сначала)
    query = query.order_by(Advertisement.created_at.desc())
    
    # Выполняем запрос
    result = await session.execute(query)
    all_ads = result.scalars().all()
    
    # Пагинация
    total = len(all_ads)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_ads = all_ads[start:end]
    
    response_data = {
        "advertisements": [ad.json for ad in paginated_ads],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }
    
    # Проверяем Accept заголовок
    accept_header = request.headers.get('Accept', '')
    if 'text/html' in accept_header:
        html = "<h1>Все объявления</h1>"
        html += f"<p>Найдено: {total} объявлений</p>"
        for ad in paginated_ads:
            html += f"""
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>{ad.title}</h3>
                <p>{ad.description}</p>
                <p><small>Владелец: {ad.owner} | Создано: {ad.created_at}</small></p>
                <a href="/advertisements/{ad.id}">Подробнее</a>
            </div>
            """
        return web.Response(text=html, content_type='text/html')
    
    return web.json_response(response_data)


async def get_advertisement(request: web.Request):
    """Получение одного объявления по ID"""
    session = request.session
    ad_id = int(request.match_info['ad_id'])
    
    ad = await get_advertisement_by_id(session, ad_id)
    
    # Проверяем Accept заголовок
    accept_header = request.headers.get('Accept', '')
    if 'text/html' in accept_header:
        html = f"""
        <h1>{ad.title}</h1>
        <p><strong>Описание:</strong> {ad.description}</p>
        <p><strong>Владелец:</strong> {ad.owner}</p>
        <p><strong>Дата создания:</strong> {ad.created_at}</p>
        <a href="/advertisements">Назад к списку</a>
        """
        return web.Response(text=html, content_type='text/html')
    
    return web.json_response(ad.json)


async def create_advertisement(request: web.Request):
    """Создание нового объявления"""
    session = request.session
    
    try:
        json_data = await request.json()
    except json.JSONDecodeError:
        raise HttpError(400, "Invalid JSON")
    
    validated_data = validate(CreateAdvertisementRequest, json_data)
    
    ad = Advertisement(
        title=validated_data["title"],
        description=validated_data["description"],
        owner=validated_data["owner"]
    )
    
    await add_advertisement(session, ad)
    
    return web.json_response(ad.id_json, status=201)


async def update_advertisement(request: web.Request):
    """Обновление объявления"""
    session = request.session
    ad_id = int(request.match_info['ad_id'])
    
    try:
        json_data = await request.json()
    except json.JSONDecodeError:
        raise HttpError(400, "Invalid JSON")
    
    validated_data = validate(UpdateAdvertisementRequest, json_data)
    ad = await get_advertisement_by_id(session, ad_id)
    
    if "title" in validated_data:
        ad.title = validated_data["title"]
    if "description" in validated_data:
        ad.description = validated_data["description"]
    if "owner" in validated_data:
        ad.owner = validated_data["owner"]
    
    await add_advertisement(session, ad)
    
    return web.json_response(ad.id_json)


async def delete_advertisement(request: web.Request):
    """Удаление объявления"""
    session = request.session
    ad_id = int(request.match_info['ad_id'])
    
    ad = await get_advertisement_by_id(session, ad_id)
    
    await session.delete(ad)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HttpError(500, str(e))
    
    return web.json_response({"status": "deleted", "id": ad_id})


async def search_advertisements(request: web.Request):
    """Поиск объявлений по заголовку и описанию"""
    session = request.session
    query_text = request.query.get('q', '')
    
    if not query_text:
        raise HttpError(400, "search query is required")
    
    # Поиск по заголовку и описанию
    search_query = select(Advertisement).where(
        or_(
            Advertisement.title.ilike(f'%{query_text}%'),
            Advertisement.description.ilike(f'%{query_text}%')
        )
    ).order_by(Advertisement.created_at.desc())
    
    result = await session.execute(search_query)
    ads = result.scalars().all()
    
    # Проверяем Accept заголовок
    accept_header = request.headers.get('Accept', '')
    if 'text/html' in accept_header:
        html = f"<h1>Результаты поиска: '{query_text}'</h1>"
        html += f"<p>Найдено: {len(ads)} объявлений</p>"
        for ad in ads:
            html += f"""
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>{ad.title}</h3>
                <p>{ad.description}</p>
                <p><small>Владелец: {ad.owner} | Создано: {ad.created_at}</small></p>
                <a href="/advertisements/{ad.id}">Подробнее</a>
            </div>
            """
        return web.Response(text=html, content_type='text/html')
    
    return web.json_response({
        "query": query_text,
        "results": [ad.json for ad in ads],
        "count": len(ads)
    })


async def index_page(request: web.Request):
    """Главная страница с документацией"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Advertisement API (aiohttp)</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            pre { background: #333; color: #fff; padding: 10px; border-radius: 5px; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>📢 REST API для объявлений (aiohttp)</h1>
        
        <div class="endpoint">
            <h2>📋 GET <a href="/advertisements">/advertisements</a></h2>
            <p>Получить все объявления</p>
            <p>Параметры: page, per_page, owner</p>
        </div>
        
        <div class="endpoint">
            <h2>➕ POST /advertisements</h2>
            <p>Создать новое объявление</p>
            <pre>curl -X POST http://localhost:8080/advertisements \\
  -H "Content-Type: application/json" \\
  -d '{"title":"Продам машину","description":"Хорошая машина","owner":"Иван"}'</pre>
        </div>
        
        <div class="endpoint">
            <h2>🔍 GET <a href="/advertisements/search?q=test">/advertisements/search?q=запрос</a></h2>
            <p>Поиск объявлений</p>
        </div>
        
        <div class="endpoint">
            <h2>📄 GET /advertisements/{id}</h2>
            <p>Получить объявление по ID</p>
            <p>Пример: <a href="/advertisements/1">/advertisements/1</a></p>
        </div>
        
        <div class="endpoint">
            <h2>✏️ PATCH /advertisements/{id}</h2>
            <p>Обновить объявление</p>
            <pre>curl -X PATCH http://localhost:8080/advertisements/1 \\
  -H "Content-Type: application/json" \\
  -d '{"description":"Отличное состояние"}'</pre>
        </div>
        
        <div class="endpoint">
            <h2>🗑️ DELETE /advertisements/{id}</h2>
            <p>Удалить объявление</p>
            <pre>curl -X DELETE http://localhost:8080/advertisements/1</pre>
        </div>
        
        <p><strong>Документация:</strong> Этот API поддерживает как JSON, так и HTML ответы.</p>
        <p><strong>Порт:</strong> 8080</p>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')


async def db_context(app: web.Application):
    """Контекст для работы с БД"""
    print("Starting database...")
    await init_db()
    yield
    await close_db()
    print("Database closed.")


def create_app():
    """Создание приложения aiohttp"""
    app = web.Application(middlewares=[error_middleware, session_middleware])
    
    # Регистрация роутов
    app.router.add_get('/', index_page)
    app.router.add_get('/advertisements', list_advertisements)
    app.router.add_get('/advertisements/{ad_id:\d+}', get_advertisement)
    app.router.add_post('/advertisements', create_advertisement)
    app.router.add_patch('/advertisements/{ad_id:\d+}', update_advertisement)
    app.router.add_delete('/advertisements/{ad_id:\d+}', delete_advertisement)
    app.router.add_get('/advertisements/search', search_advertisements)
    
    # Контекст базы данных
    app.cleanup_ctx.append(db_context)
    
    return app


if __name__ == '__main__':
    print("\n" + "="*50)
    print("📢 Advertisement API (aiohttp) запущен!")
    print(f"🌐 Адрес: http://localhost:8080")
    print("="*50 + "\n")
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=8080)