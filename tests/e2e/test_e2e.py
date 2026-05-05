import os
import pytest
from playwright.sync_api import Page, expect


BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture
def conversation_id(page: Page) -> int:
    page.goto(BASE_URL)
    page.click("#new-conv-btn")
    page.wait_for_selector(".conv-item")
    item = page.locator(".conv-item").first
    return int(item.get_attribute("data-id"))


def test_crear_conversacion(page: Page):
    page.goto(BASE_URL)
    page.click("#new-conv-btn")
    expect(page.locator(".conv-item")).to_be_visible()
    expect(page.locator("#prompt")).to_be_enabled()
    expect(page.locator("#send")).to_be_enabled()


def test_enviar_y_recibir_mensaje(page: Page, conversation_id: int):
    page.goto(BASE_URL)
    page.click(f'.conv-item[data-id="{conversation_id}"]')
    page.fill("#prompt", "Hola, ¿cómo estás?")
    page.click("#send")
    page.wait_for_selector(".message.user")
    expect(page.locator(".message.user .bubble")).to_contain_text("Hola")


def test_lista_conversaciones_persisted(page: Page, conversation_id: int):
    page.goto(BASE_URL)
    expect(page.locator(f'.conv-item[data-id="{conversation_id}"]')).to_be_visible()


def test_cambiar_entre_conversaciones(page: Page):
    page.goto(BASE_URL)
    page.click("#new-conv-btn")
    page.wait_for_timeout(200)
    page.click("#new-conv-btn")
    page.wait_for_timeout(200)
    items = page.locator(".conv-item")
    expect(items).to_have_count(2) #
