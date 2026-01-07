# [file name]: server_async.py
# [file content begin]
from aiohttp import web
import json
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError

from models_async import Session, Advertisement, User, init_db, close_db
from schema import validate, CreateAdvertisementRequest, UpdateAdvertisementRequest, UserCreate, UserLogin
from errors import HttpError
from auth import create_jwt_token, decode_jwt_token


@web.middleware
async def error_middleware(request: web.Request, handler):
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
    async with Session() as session:
        request.session = session
        response = await handler(request)
        return response


async def add_advertisement(session, ad: Advertisement):
    session.add(ad)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HttpError(409, "database error")
    except Exception as e:
        await session.rollback()
        raise HttpError(500, str(e))


async def register_user(request: web.Request):
    session = request.session
    
    try:
        json_data = await request.json()
    except json.JSONDecodeError:
        raise HttpError(400, "Invalid JSON")
    
    validated_data = validate(UserCreate, json_data)
    
    result = await session.execute(
        select(User).where(User.email == validated_data["email"])
    )
    if result.scalar_one_or_none():
        raise HttpError(409, "User already exists")
    
    user = User(email=validated_data["email"])
    user.set_password(validated_data["password"])
    
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HttpError(409, "database error")
    
    token = create_jwt_token(user.id)
    return web.json_response({"token": token, "user_id": user.id})


async def login_user(request: web.Request):
    session = request.session
    
    try:
        json_data = await request.json()
    except json.JSONDecodeError:
        raise HttpError(400, "Invalid JSON")
    
    validated_data = validate(UserLogin, json_data)
    
    result = await session.execute(
        select(User).where(User.email == validated_data["email"])
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.check_password(validated_data["password"]):
        raise HttpError(401, "Invalid credentials")
    
    token = create_jwt_token(user.id)
    return web.json_response({"token": token, "user_id": user.id})


def get_user_id_from_token(request: web.Request) -> int:
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HttpError(401, "Authorization required")
    
    token = auth_header.split(' ')[1]
    payload = decode_jwt_token(token)
    return payload['user_id']


async def list_advertisements(request: web.Request):
    """Получение всех объявлений с пагинацией"""
    session = request.session
    
    # Проверяем, что запрашивает клиент
    accept_header = request.headers.get('Accept', '').lower()
    format_param = request.query.get('format', '').lower()
    
    # Определяем, показывать ли HTML
    show_html = False
    if format_param == 'html':
        show_html = True
    elif 'text/html' in accept_header and 'application/json' not in accept_header:
        show_html = True
    
    # Пагинация
    try:
        page = int(request.query.get('page', 1))
        per_page = int(request.query.get('per_page', 10))
    except ValueError:
        raise HttpError(400, "page and per_page must be integers")
    
    # Фильтрация по пользователю
    user_id = request.query.get('user_id')
    
    # Создаем запрос
    query = select(Advertisement)
    
    if user_id:
        try:
            user_id_int = int(user_id)
            query = query.where(Advertisement.user_id == user_id_int)
        except ValueError:
            raise HttpError(400, "user_id must be an integer")
    
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
    
    # Проверяем, авторизован ли пользователь
    current_user_id = None
    try:
        current_user_id = get_user_id_from_token(request)
    except HttpError:
        pass
    
    # Если нужно показать HTML
    if show_html:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Список объявлений</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1 {
                    color: #333;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                }
                .ad {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 15px 0;
                    background: #f9f9f9;
                }
                .ad h3 {
                    margin-top: 0;
                    color: #444;
                }
                .ad-meta {
                    color: #666;
                    font-size: 0.9em;
                    margin: 10px 0;
                }
                .actions {
                    margin-top: 10px;
                }
                .actions a {
                    display: inline-block;
                    padding: 5px 10px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 3px;
                    margin-right: 5px;
                }
                .own-badge {
                    background: #4CAF50;
                    color: white;
                    padding: 2px 6px;
                    border-radius: 10px;
                    font-size: 0.8em;
                    margin-left: 10px;
                }
                .stats {
                    background: #e9f7fe;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 15px 0;
                }
                .format-links {
                    margin: 10px 0;
                }
                .format-links a {
                    color: #667eea;
                    text-decoration: none;
                    margin-right: 15px;
                }
            </style>
        </head>
        <body>
            <h1>📢 Все объявления</h1>
            
            <div class="format-links">
                <a href="/">🏠 На главную</a>
                <a href="/advertisements">📊 JSON версия</a>
            </div>
            
            <div class="stats">
                <strong>Статистика:</strong>
                Всего объявлений: """ + str(total) + """<br>
                Страница """ + str(page) + """ из """ + str((total + per_page - 1) // per_page) + """<br>
                Показано: """ + str(len(paginated_ads)) + """ объявлений
            </div>
        """
        
        for ad in paginated_ads:
            is_owner = (current_user_id == ad.user_id) if current_user_id else False
            created_at_str = ad.created_at.strftime('%d.%m.%Y %H:%M') if ad.created_at else 'не указано'
            
            html += f"""
            <div class="ad">
                <h3>
                    {ad.title}
                    {f'<span class="own-badge">Ваше</span>' if is_owner else ''}
                </h3>
                <p>{ad.description}</p>
                <div class="ad-meta">
                    📅 Создано: {created_at_str}<br>
                    👤 ID пользователя: {ad.user_id}
                </div>
                <div class="actions">
                    <a href="/advertisements/{ad.id}?format=html">Подробнее</a>
                </div>
            </div>
            """
        
        # Добавляем пагинацию
        total_pages = (total + per_page - 1) // per_page
        if total_pages > 1:
            html += '<div class="pagination" style="margin-top: 20px;">'
            for p in range(1, total_pages + 1):
                if p == page:
                    html += f'<span style="margin: 0 5px; font-weight: bold;">{p}</span>'
                else:
                    html += f'<a href="/advertisements?format=html&page={p}&per_page={per_page}" style="margin: 0 5px;">{p}</a>'
            html += '</div>'
        
        html += """
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    # Если не HTML, возвращаем JSON
    advertisements_data = []
    for ad in paginated_ads:
        ad_data = ad.json
        ad_data['is_owner'] = (current_user_id == ad.user_id) if current_user_id else False
        advertisements_data.append(ad_data)
    
    response_data = {
        "advertisements": advertisements_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }
    
    return web.json_response(response_data)


async def get_advertisement(request: web.Request):
    """Получение одного объявления по ID"""
    session = request.session
    ad_id = int(request.match_info['ad_id'])
    
    # Получаем объявление
    ad = await session.get(Advertisement, ad_id)
    if ad is None:
        raise HttpError(404, "advertisement not found")
    
    # Проверяем формат
    accept_header = request.headers.get('Accept', '').lower()
    format_param = request.query.get('format', '').lower()
    
    # Определяем, показывать ли HTML
    show_html = False
    if format_param == 'html':
        show_html = True
    elif 'text/html' in accept_header and 'application/json' not in accept_header:
        show_html = True
    
    # Проверяем, авторизован ли пользователь
    current_user_id = None
    try:
        current_user_id = get_user_id_from_token(request)
    except HttpError:
        pass
    
    if show_html:
        is_owner = (current_user_id == ad.user_id) if current_user_id else False
        created_at_str = ad.created_at.strftime('%d.%m.%Y %H:%M') if ad.created_at else 'не указано'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{ad.title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{ color: #333; }}
                .ad-details {{
                    background: #f9f9f9;
                    padding: 20px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .actions a {{
                    display: inline-block;
                    padding: 8px 15px;
                    margin-right: 10px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 3px;
                }}
                .own-badge {{
                    background: #4CAF50;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 12px;
                    font-size: 0.9em;
                    margin-left: 10px;
                }}
                .format-links {{
                    margin: 20px 0;
                }}
                .format-links a {{
                    color: #667eea;
                    text-decoration: none;
                    margin-right: 15px;
                }}
            </style>
        </head>
        <body>
            <h1>
                {ad.title}
                {f'<span class="own-badge">Ваше объявление</span>' if is_owner else ''}
            </h1>
            
            <div class="format-links">
                <a href="/advertisements/{ad.id}">📊 JSON версия</a>
                <a href="/advertisements">← Назад к списку</a>
            </div>
            
            <div class="ad-details">
                <p><strong>Описание:</strong></p>
                <p>{ad.description}</p>
                
                <p><strong>Детали:</strong></p>
                <ul>
                    <li><strong>ID объявления:</strong> {ad.id}</li>
                    <li><strong>ID пользователя:</strong> {ad.user_id}</li>
                    <li><strong>Дата создания:</strong> {created_at_str}</li>
                    <li><strong>Принадлежит вам:</strong> {'Да' if is_owner else 'Нет'}</li>
                </ul>
            </div>
            
            <div style="margin-top: 30px;">
                <a href="/">🏠 На главную</a>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    # JSON ответ
    response_data = ad.json
    response_data['is_owner'] = (current_user_id == ad.user_id) if current_user_id else False
    
    return web.json_response(response_data)


async def create_advertisement(request: web.Request):
    session = request.session
    
    user_id = get_user_id_from_token(request)
    
    try:
        json_data = await request.json()
    except json.JSONDecodeError:
        raise HttpError(400, "Invalid JSON")
    
    validated_data = validate(CreateAdvertisementRequest, json_data)
    
    ad = Advertisement(
        title=validated_data["title"],
        description=validated_data["description"],
        user_id=user_id
    )
    
    await add_advertisement(session, ad)
    
    return web.json_response({"id": ad.id}, status=201)


async def update_advertisement(request: web.Request):
    """Обновление объявления"""
    session = request.session
    ad_id = int(request.match_info['ad_id'])
    
    user_id = get_user_id_from_token(request)
    
    try:
        json_data = await request.json()
    except json.JSONDecodeError:
        raise HttpError(400, "Invalid JSON")
    
    validated_data = validate(UpdateAdvertisementRequest, json_data)
    
    # Получаем объявление по ID
    ad = await session.get(Advertisement, ad_id)
    if ad is None:
        raise HttpError(404, "advertisement not found")
    
    if ad.user_id != user_id:
        raise HttpError(403, "You can only edit your own advertisements")
    
    if "title" in validated_data:
        ad.title = validated_data["title"]
    if "description" in validated_data:
        ad.description = validated_data["description"]
    
    session.add(ad)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HttpError(409, "database error")
    except Exception as e:
        await session.rollback()
        raise HttpError(500, str(e))
    
    return web.json_response({"id": ad.id})


async def delete_advertisement(request: web.Request):
    """Удаление объявления"""
    session = request.session
    ad_id = int(request.match_info['ad_id'])
    
    user_id = get_user_id_from_token(request)
    
    # Получаем объявление по ID
    ad = await session.get(Advertisement, ad_id)
    if ad is None:
        raise HttpError(404, "advertisement not found")
    
    if ad.user_id != user_id:
        raise HttpError(403, "You can only delete your own advertisements")
    
    await session.delete(ad)
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HttpError(500, str(e))
    
    # Возвращаем статус 204 No Content без тела
    return web.Response(status=204)


async def search_advertisements(request: web.Request):
    """Поиск объявлений по заголовку и описанию"""
    session = request.session
    query_text = request.query.get('q', '')
    
    if not query_text:
        raise HttpError(400, "search query is required")
    
    # Проверяем формат
    accept_header = request.headers.get('Accept', '').lower()
    format_param = request.query.get('format', '').lower()
    
    show_html = False
    if format_param == 'html':
        show_html = True
    elif 'text/html' in accept_header and 'application/json' not in accept_header:
        show_html = True
    
    # Поиск по заголовку и описанию
    search_query = select(Advertisement).where(
        or_(
            Advertisement.title.ilike(f'%{query_text}%'),
            Advertisement.description.ilike(f'%{query_text}%')
        )
    ).order_by(Advertisement.created_at.desc())
    
    result = await session.execute(search_query)
    ads = result.scalars().all()
    
    # Проверяем, авторизован ли пользователь
    current_user_id = None
    try:
        current_user_id = get_user_id_from_token(request)
    except HttpError:
        pass
    
    if show_html:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Поиск: {query_text}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{ color: #333; }}
                .search-results {{
                    margin: 20px 0;
                }}
                .ad {{
                    border: 1px solid #ddd;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                }}
                .no-results {{
                    color: #666;
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <h1>🔍 Результаты поиска: "{query_text}"</h1>
            <p>Найдено: {len(ads)} объявлений</p>
            
            <div class="search-results">
        """
        
        if not ads:
            html += '<p class="no-results">Ничего не найдено</p>'
        else:
            for ad in ads:
                is_owner = (current_user_id == ad.user_id) if current_user_id else False
                created_at_str = ad.created_at.strftime('%d.%m.%Y %H:%M') if ad.created_at else 'не указано'
                
                html += f"""
                <div class="ad">
                    <h3>{ad.title}</h3>
                    <p>{ad.description}</p>
                    <p><small>User ID: {ad.user_id} | Создано: {created_at_str}</small></p>
                    <a href="/advertisements/{ad.id}?format=html">Подробнее</a>
                </div>
                """
        
        html += """
            </div>
            <a href="/advertisements?format=html">← Назад к списку</a>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    # JSON ответ
    results = []
    for ad in ads:
        ad_data = ad.json
        ad_data['is_owner'] = (current_user_id == ad.user_id) if current_user_id else False
        results.append(ad_data)
    
    return web.json_response({
        "query": query_text,
        "results": results,
        "count": len(ads)
    })


async def index_page(request: web.Request):
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
            .format-links { margin: 20px 0; }
            .format-links a { 
                display: inline-block;
                padding: 10px 20px;
                margin-right: 10px;
                background: #667eea;
                color: white;
                border-radius: 5px;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <h1>📢 REST API для объявлений (aiohttp)</h1>
        
        <div class="format-links">
            <a href="/advertisements">📋 Просмотреть объявления</a>
            <a href="/advertisements?format=html">🌐 HTML версия</a>
        </div>
        
        <div class="endpoint">
            <h2>📝 POST /register</h2>
            <p>Регистрация пользователя</p>
            <pre>curl -X POST http://localhost:8080/register \\
  -H "Content-Type: application/json" \\
  -d '{"email":"user@example.com","password":"password"}'</pre>
        </div>
        
        <div class="endpoint">
            <h2>🔑 POST /login</h2>
            <p>Вход пользователя (получение JWT токена)</p>
            <pre>curl -X POST http://localhost:8080/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"user@example.com","password":"password"}'</pre>
        </div>
        
        <div class="endpoint">
            <h2>📋 GET <a href="/advertisements">/advertisements</a></h2>
            <p>Получить все объявления</p>
            <p>Поддерживает пагинацию: <code>?page=1&per_page=10</code></p>
            <p>Фильтрация по пользователю: <code>?user_id=1</code></p>
        </div>
        
        <div class="endpoint">
            <h2>➕ POST /advertisements</h2>
            <p>Создать новое объявление (требуется токен)</p>
            <pre>curl -X POST http://localhost:8080/advertisements \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -d '{"title":"Продам машину","description":"Хорошая машина"}'</pre>
        </div>
        
        <div class="endpoint">
            <h2>🔍 GET <a href="/advertisements/search?q=test">/advertisements/search?q=запрос</a></h2>
            <p>Поиск объявлений</p>
        </div>
        
        <div class="endpoint">
            <h2>📄 GET <a href="/advertisements/1">/advertisements/{id}</a></h2>
            <p>Получить объявление по ID</p>
            <p>Пример: <a href="/advertisements/1">/advertisements/1</a></p>
        </div>
        
        <div class="endpoint">
            <h2>✏️ PATCH /advertisements/{id}</h2>
            <p>Обновить объявление (только владелец)</p>
            <pre>curl -X PATCH http://localhost:8080/advertisements/1 \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -d '{"description":"Отличное состояние"}'</pre>
        </div>
        
        <div class="endpoint">
            <h2>🗑️ DELETE /advertisements/{id}</h2>
            <p>Удалить объявление (только владелец, возвращает 204)</p>
            <pre>curl -X DELETE http://localhost:8080/advertisements/1 \\
  -H "Authorization: Bearer YOUR_TOKEN"</pre>
        </div>
        
        <p><strong>Форматы:</strong> По умолчанию API возвращает JSON. Добавьте <code>?format=html</code> для HTML версии.</p>
        <p><strong>Аутентификация:</strong> Используйте токен из <code>/login</code> в заголовке <code>Authorization: Bearer &lt;token&gt;</code></p>
        <p><strong>Порт:</strong> 8080</p>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')


async def db_context(app: web.Application):
    """Контекст для работы с БД"""
    print("📦 Starting database...")
    await init_db()
    print("✅ Database initialized successfully.")
    
    # Важно: yield должен что-то возвращать!
    yield {"db": "ready"}
    
    print("📦 Closing database...")
    await close_db()
    print("✅ Database closed.")


def create_app():
    app = web.Application(middlewares=[error_middleware, session_middleware])
    
    # Регистрация роутов
    app.router.add_get('/', index_page)
    app.router.add_post('/register', register_user)
    app.router.add_post('/login', login_user)
    app.router.add_get('/advertisements', list_advertisements)
    app.router.add_get('/advertisements/{ad_id:\d+}', get_advertisement)
    app.router.add_post('/advertisements', create_advertisement)
    app.router.add_patch('/advertisements/{ad_id:\d+}', update_advertisement)
    app.router.add_delete('/advertisements/{ad_id:\d+}', delete_advertisement)
    app.router.add_get('/advertisements/search', search_advertisements)
    
    # Добавляем контекст базы данных
    app.cleanup_ctx.append(db_context)
    
    return app


if __name__ == '__main__':
    print("\n" + "="*50)
    print("📢 Advertisement API (aiohttp) запущен!")
    print(f"🌐 Адрес: http://localhost:8080")
    print("🔐 Аутентификация через JWT")
    print("📊 JSON по умолчанию, ?format=html для HTML версии")
    print("="*50 + "\n")
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=8080)
# [file content end]