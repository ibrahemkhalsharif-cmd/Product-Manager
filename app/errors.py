"""Safe Arabic error pages. Details go to the server log, never to the browser."""
from __future__ import annotations

import pymysql
from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

MESSAGES = {
    400: ("طلب غير صالح", "تعذّر فهم الطلب. تحقق من البيانات وحاول مرة أخرى."),
    404: ("الصفحة غير موجودة", "الصفحة التي تبحث عنها غير موجودة أو تم نقلها."),
    405: ("طريقة غير مسموحة", "هذا الإجراء غير مسموح به في هذه الصفحة."),
    413: ("الطلب كبير جدًا", "حجم البيانات المرسلة أكبر من المسموح."),
    500: ("حدث خطأ غير متوقع", "حدث خطأ في الخادم. حاول مرة أخرى لاحقًا."),
    503: ("الخدمة غير متاحة", "تعذّر الاتصال بقاعدة البيانات حاليًا. حاول مرة أخرى بعد قليل."),
}
CSRF_MESSAGE = ("انتهت صلاحية الصفحة", "أعد تحميل الصفحة ثم حاول مرة أخرى.")


def _page(status: int, title: str, message: str):
    return render_template("error.html", status=status, title=title, message=message), status


def init_app(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def handle_csrf(_exc):
        return _page(400, *CSRF_MESSAGE)

    @app.errorhandler(HTTPException)
    def handle_http(exc):
        status = exc.code or 500
        key = status if status in MESSAGES else (400 if status < 500 else 500)
        return _page(status, *MESSAGES[key])

    @app.errorhandler(pymysql.MySQLError)
    def handle_database(_exc):
        app.logger.exception("Database error")
        return _page(503, *MESSAGES[503])

    @app.errorhandler(Exception)
    def handle_unexpected(_exc):
        app.logger.exception("Unhandled error")
        return _page(500, *MESSAGES[500])
