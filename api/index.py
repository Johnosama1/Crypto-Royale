import sys
import os
import asyncio
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, Response
from telegram import Update

flask_app = Flask(__name__)

_ptb_app = None

def get_ptb_app():
    global _ptb_app
    if _ptb_app is None:
        import bot as bot_module
        _ptb_app = bot_module.build_application()
    return _ptb_app


@flask_app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        ptb = get_ptb_app()
        data = request.get_json(force=True)
        update = Update.de_json(data, ptb.bot)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(ptb.initialize())
            loop.run_until_complete(ptb.process_update(update))
        finally:
            loop.close()

        return Response("OK", status=200)
    except Exception as e:
        logging.exception(e)
        return Response("Error", status=500)


@flask_app.route("/", methods=["GET"])
@flask_app.route("/api", methods=["GET"])
def health():
    return Response("Crypto Royale Bot is running!", status=200)


def handler(req, res):
    with flask_app.test_request_context(
        path=req.get("path", "/"),
        method=req.get("method", "GET"),
        headers=req.get("headers", {}),
        data=json.dumps(req.get("body", {})),
        content_type="application/json",
    ):
        response = flask_app.full_dispatch_request()
        res["statusCode"] = response.status_code
        res["body"] = response.get_data(as_text=True)
        res["headers"] = dict(response.headers)
    return res
