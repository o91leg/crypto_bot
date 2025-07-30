"""
Путь: src/data/models/base_model.py
Описание: Базовая модель для всех таблиц БД с общими полями и методами
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, func
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.orm import Mapped, mapped_column


@as_declarative()
class Base:
    """Базовый класс для всех моделей."""

    # Генерация имени таблицы из имени класса
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + 's'

    # Общие поля для всех таблиц
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата создания записи"
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
        comment="Дата последнего обновления записи"
    )

    def to_dict(self, exclude_fields: Optional[list] = None) -> Dict[str, Any]:
        """
        Преобразование модели в словарь.

        Args:
            exclude_fields: Список полей для исключения

        Returns:
            Dict[str, Any]: Словарь с данными модели
        """
        exclude_fields = exclude_fields or []

        result = {}
        for column in self.__table__.columns:
            field_name = column.name
            if field_name not in exclude_fields:
                value = getattr(self, field_name)

                # Обработка datetime объектов
                if isinstance(value, datetime):
                    result[field_name] = value.isoformat()
                else:
                    result[field_name] = value

        return result

    def update_from_dict(self, data: Dict[str, Any], exclude_fields: Optional[list] = None) -> None:
        """
        Обновление модели из словаря.

        Args:
            data: Словарь с новыми данными
            exclude_fields: Список полей для исключения
        """
        exclude_fields = exclude_fields or ['id', 'created_at', 'updated_at']

        for key, value in data.items():
            if hasattr(self, key) and key not in exclude_fields:
                setattr(self, key, value)

    def __repr__(self) -> str:
        """
        Строковое представление модели.

        Returns:
            str: Строковое представление
        """
        class_name = self.__class__.__name__

        # Пытаемся найти основное поле для отображения
        primary_field = None
        if hasattr(self, 'id'):
            primary_field = f"id={self.id}"
        elif hasattr(self, 'symbol'):
            primary_field = f"symbol={self.symbol}"
        elif hasattr(self, 'user_id'):
            primary_field = f"user_id={self.user_id}"

        if primary_field:
            return f"<{class_name}({primary_field})>"
        else:
            return f"<{class_name}()>"


class TimestampMixin:
    """Миксин для моделей, требующих отслеживания времени создания и обновления."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата создания записи"
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
        comment="Дата последнего обновления записи"
    )


class SoftDeleteMixin:
    """Миксин для мягкого удаления записей."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата удаления записи (для мягкого удаления)"
    )

    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Флаг удаления записи"
    )

    def soft_delete(self) -> None:
        """Мягкое удаление записи."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Восстановление удаленной записи."""
        self.is_deleted = False
        self.deleted_at = None


def get_table_name(model_class: type) -> str:
    """
    Получить имя таблицы для модели.

    Args:
        model_class: Класс модели

    Returns:
        str: Имя таблицы
    """
    if hasattr(model_class, '__tablename__'):
        return model_class.__tablename__
    else:
        return model_class.__name__.lower() + 's'


def create_all_tables(engine):
    """
    Создать все таблицы в базе данных.

    Args:
        engine: SQLAlchemy engine
    """
    from sqlalchemy import MetaData

    metadata = MetaData()
    Base.metadata.create_all(bind=engine, checkfirst=True)


def drop_all_tables(engine):
    """
    Удалить все таблицы из базы данных.

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.drop_all(bind=engine)