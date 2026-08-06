def test_theme_toggle_is_wired(client):
    html = client.get("/").get_data(as_text=True)
    assert "theme-toggle" in html
    assert "toggleTheme" in html
    assert "data-theme" in html
    css = client.get("/static/css/site.css").get_data(as_text=True)
    assert '[data-theme="light"]' in css
    assert "hero-grad-float" in css
    assert "--purple: #9b6dff" in css
    js = client.get("/static/js/app.js").get_data(as_text=True)
    assert "toggleTheme" in js and "localStorage" in js and "data-theme" in js


def test_home_hero_side_cards_and_float_dots(client):
    html = client.get("/").get_data(as_text=True)
    assert "hero-layout" in html
    assert "hero-side" in html
    assert "float-dot" in html
    assert "hero-grad" in html
    assert "SEU-Monash Joint International School" in html
    assert "nav-ico" in html
    assert "f1" in html and "f6" in html
    css = client.get("/static/css/site.css").get_data(as_text=True)
    assert "dot-drift" in css
    assert "card-drift-a" in css and "card-drift-d" in css
    assert "border-radius: 32px" in css


def test_no_emoji_in_templates(client):
    html = client.get("/").get_data(as_text=True)
    for emoji in ["🧭", "🗺", "🤝", "📖", "🌍", "💡", "✓", "☀", "🌙"]:
        assert emoji not in html, f"emoji {emoji} should not appear on homepage"
    js = client.get("/static/js/app.js").get_data(as_text=True)
    assert "btn.innerHTML" in js
    assert "ico-sun" in js and "ico-moon" in js
