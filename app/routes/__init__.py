def register_blueprints(app):
    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .english_hub import bp as english_bp
    from .guides import bp as guides_bp
    from .main import bp as main_bp
    from .posts import bp as posts_bp
    from .tutoring import bp as tutoring_bp
    from .surveys import bp as surveys_bp
    from .survey_admin import bp as survey_admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(guides_bp)
    app.register_blueprint(english_bp)
    app.register_blueprint(tutoring_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(surveys_bp)
    app.register_blueprint(survey_admin_bp)
