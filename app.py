"""Entrypoint para Vercel (busca una instancia Flask llamada `app`)."""
from radar.web import create_app

app = create_app()
