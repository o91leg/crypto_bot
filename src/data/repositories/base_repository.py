"""
Путь: src/data/repositories/base_repository.py
Описание: Базовый репозиторий с общими CRUD операциями для всех моделей
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Generic, TypeVar, Type, List, Optional, Any, Dict
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound
import structlog

from data.models.base_model import Base
from utils.exceptions import RecordNotFoundError, RecordAlreadyExistsError, DatabaseError

# Настройка логирования
logger = structlog.get_logger(__name__)

# Типизация для Generic репозитория
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Базовый репозиторий с общими CRUD операциями."""

    def __init__(self, model: Type[ModelType]):
        """
        Инициализация репозитория.

        Args:
            model: Класс модели SQLAlchemy
        """
        self.model = model

    async def create(self, session: AsyncSession, **kwargs) -> ModelType:
        """
        Создать новую запись.

        Args:
            session: Сессия базы данных
            **kwargs: Данные для создания записи

        Returns:
            ModelType: Созданная запись

        Raises:
            RecordAlreadyExistsError: Если запись уже существует
            DatabaseError: При других ошибках БД
        """
        try:
            instance = self.model(**kwargs)
            session.add(instance)
            await session.flush()

            logger.debug(
                "Record created",
                model=self.model.__name__,
                record_id=getattr(instance, 'id', None)
            )

            return instance

        except IntegrityError as e:
            await session.rollback()
            logger.error(
                "Failed to create record - integrity error",
                model=self.model.__name__,
                error=str(e)
            )
            raise RecordAlreadyExistsError(
                self.model.__name__,
                kwargs.get('id', 'unknown')
            )

        except Exception as e:
            await session.rollback()
            logger.error(
                "Failed to create record",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to create {self.model.__name__}: {str(e)}")

    async def get_by_id(self, session: AsyncSession, record_id: Any, load_relations: bool = False) -> Optional[ModelType]:
        """
        Получить запись по ID.

        Args:
            session: Сессия базы данных
            record_id: ID записи
            load_relations: Загружать ли связанные объекты

        Returns:
            Optional[ModelType]: Найденная запись или None
        """
        try:
            stmt = select(self.model).where(self.model.id == record_id)

            if load_relations:
                # Автоматически загружаем все связи
                stmt = self._add_relationship_loading(stmt)

            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                logger.debug(
                    "Record found by ID",
                    model=self.model.__name__,
                    record_id=record_id
                )
            else:
                logger.debug(
                    "Record not found by ID",
                    model=self.model.__name__,
                    record_id=record_id
                )

            return instance

        except Exception as e:
            logger.error(
                "Failed to get record by ID",
                model=self.model.__name__,
                record_id=record_id,
                error=str(e)
            )
            raise DatabaseError(f"Failed to get {self.model.__name__} by ID: {str(e)}")

    async def get_by_field(
        self,
        session: AsyncSession,
        field_name: str,
        field_value: Any,
        load_relations: bool = False
    ) -> Optional[ModelType]:
        """
        Получить запись по значению поля.

        Args:
            session: Сессия базы данных
            field_name: Название поля
            field_value: Значение поля
            load_relations: Загружать ли связанные объекты

        Returns:
            Optional[ModelType]: Найденная запись или None
        """
        try:
            field = getattr(self.model, field_name)
            stmt = select(self.model).where(field == field_value)

            if load_relations:
                stmt = self._add_relationship_loading(stmt)

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        except AttributeError:
            logger.error(
                "Field not found in model",
                model=self.model.__name__,
                field_name=field_name
            )
            raise DatabaseError(f"Field {field_name} not found in {self.model.__name__}")

        except Exception as e:
            logger.error(
                "Failed to get record by field",
                model=self.model.__name__,
                field_name=field_name,
                error=str(e)
            )
            raise DatabaseError(f"Failed to get {self.model.__name__} by {field_name}: {str(e)}")

    async def get_all(
        self,
        session: AsyncSession,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        load_relations: bool = False
    ) -> List[ModelType]:
        """
        Получить все записи.

        Args:
            session: Сессия базы данных
            limit: Максимальное количество записей
            offset: Смещение
            load_relations: Загружать ли связанные объекты

        Returns:
            List[ModelType]: Список записей
        """
        try:
            stmt = select(self.model)

            if load_relations:
                stmt = self._add_relationship_loading(stmt)

            if offset:
                stmt = stmt.offset(offset)

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            records = list(result.scalars().all())

            logger.debug(
                "Retrieved all records",
                model=self.model.__name__,
                count=len(records),
                limit=limit,
                offset=offset
            )

            return records

        except Exception as e:
            logger.error(
                "Failed to get all records",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to get all {self.model.__name__}: {str(e)}")

    async def update(
        self,
        session: AsyncSession,
        record_id: Any,
        **kwargs
    ) -> Optional[ModelType]:
        """
        Обновить запись по ID.

        Args:
            session: Сессия базы данных
            record_id: ID записи
            **kwargs: Данные для обновления

        Returns:
            Optional[ModelType]: Обновленная запись или None

        Raises:
            RecordNotFoundError: Если запись не найдена
        """
        try:
            # Сначала проверяем существование записи
            instance = await self.get_by_id(session, record_id)
            if not instance:
                raise RecordNotFoundError(self.model.__name__, record_id)

            # Обновляем поля
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)

            await session.flush()

            logger.debug(
                "Record updated",
                model=self.model.__name__,
                record_id=record_id,
                updated_fields=list(kwargs.keys())
            )

            return instance

        except RecordNotFoundError:
            raise

        except Exception as e:
            await session.rollback()
            logger.error(
                "Failed to update record",
                model=self.model.__name__,
                record_id=record_id,
                error=str(e)
            )
            raise DatabaseError(f"Failed to update {self.model.__name__}: {str(e)}")

    async def delete(self, session: AsyncSession, record_id: Any) -> bool:
        """
        Удалить запись по ID.

        Args:
            session: Сессия базы данных
            record_id: ID записи

        Returns:
            bool: True если запись была удалена

        Raises:
            RecordNotFoundError: Если запись не найдена
        """
        try:
            # Сначала проверяем существование записи
            instance = await self.get_by_id(session, record_id)
            if not instance:
                raise RecordNotFoundError(self.model.__name__, record_id)

            await session.delete(instance)
            await session.flush()

            logger.debug(
                "Record deleted",
                model=self.model.__name__,
                record_id=record_id
            )

            return True

        except RecordNotFoundError:
            raise

        except Exception as e:
            await session.rollback()
            logger.error(
                "Failed to delete record",
                model=self.model.__name__,
                record_id=record_id,
                error=str(e)
            )
            raise DatabaseError(f"Failed to delete {self.model.__name__}: {str(e)}")

    async def bulk_create(self, session: AsyncSession, records_data: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Создать множественные записи за одну операцию.

        Args:
            session: Сессия базы данных
            records_data: Список данных для создания записей

        Returns:
            List[ModelType]: Список созданных записей
        """
        try:
            instances = []
            for record_data in records_data:
                instance = self.model(**record_data)
                instances.append(instance)
                session.add(instance)

            await session.flush()

            logger.debug(
                "Bulk records created",
                model=self.model.__name__,
                count=len(instances)
            )

            return instances

        except Exception as e:
            await session.rollback()
            logger.error(
                "Failed to bulk create records",
                model=self.model.__name__,
                count=len(records_data),
                error=str(e)
            )
            raise DatabaseError(f"Failed to bulk create {self.model.__name__}: {str(e)}")

    async def bulk_update(
        self,
        session: AsyncSession,
        filter_criteria: Dict[str, Any],
        update_data: Dict[str, Any]
    ) -> int:
        """
        Обновить множественные записи по критериям.

        Args:
            session: Сессия базы данных
            filter_criteria: Критерии фильтрации
            update_data: Данные для обновления

        Returns:
            int: Количество обновленных записей
        """
        try:
            # Формируем WHERE условие
            where_conditions = []
            for field_name, field_value in filter_criteria.items():
                field = getattr(self.model, field_name)
                where_conditions.append(field == field_value)

            stmt = update(self.model).where(and_(*where_conditions)).values(**update_data)
            result = await session.execute(stmt)

            updated_count = result.rowcount

            logger.debug(
                "Bulk records updated",
                model=self.model.__name__,
                updated_count=updated_count,
                criteria=filter_criteria
            )

            return updated_count

        except Exception as e:
            await session.rollback()
            logger.error(
                "Failed to bulk update records",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to bulk update {self.model.__name__}: {str(e)}")

    async def bulk_delete(self, session: AsyncSession, filter_criteria: Dict[str, Any]) -> int:
        """
        Удалить множественные записи по критериям.

        Args:
            session: Сессия базы данных
            filter_criteria: Критерии фильтрации

        Returns:
            int: Количество удаленных записей
        """
        try:
            # Формируем WHERE условие
            where_conditions = []
            for field_name, field_value in filter_criteria.items():
                field = getattr(self.model, field_name)
                where_conditions.append(field == field_value)

            stmt = delete(self.model).where(and_(*where_conditions))
            result = await session.execute(stmt)

            deleted_count = result.rowcount

            logger.debug(
                "Bulk records deleted",
                model=self.model.__name__,
                deleted_count=deleted_count,
                criteria=filter_criteria
            )

            return deleted_count

        except Exception as e:
            await session.rollback()
            logger.error(
                "Failed to bulk delete records",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to bulk delete {self.model.__name__}: {str(e)}")

    async def count(self, session: AsyncSession, filter_criteria: Optional[Dict[str, Any]] = None) -> int:
        """
        Подсчитать количество записей.

        Args:
            session: Сессия базы данных
            filter_criteria: Критерии фильтрации (опционально)

        Returns:
            int: Количество записей
        """
        try:
            stmt = select(func.count(self.model.id))

            if filter_criteria:
                where_conditions = []
                for field_name, field_value in filter_criteria.items():
                    field = getattr(self.model, field_name)
                    where_conditions.append(field == field_value)
                stmt = stmt.where(and_(*where_conditions))

            result = await session.execute(stmt)
            count = result.scalar()

            logger.debug(
                "Records counted",
                model=self.model.__name__,
                count=count,
                criteria=filter_criteria
            )

            return count

        except Exception as e:
            logger.error(
                "Failed to count records",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to count {self.model.__name__}: {str(e)}")

    async def exists(self, session: AsyncSession, filter_criteria: Dict[str, Any]) -> bool:
        """
        Проверить существование записи по критериям.

        Args:
            session: Сессия базы данных
            filter_criteria: Критерии поиска

        Returns:
            bool: True если запись существует
        """
        try:
            where_conditions = []
            for field_name, field_value in filter_criteria.items():
                field = getattr(self.model, field_name)
                where_conditions.append(field == field_value)

            stmt = select(func.count(self.model.id)).where(and_(*where_conditions))
            result = await session.execute(stmt)
            count = result.scalar()

            return count > 0

        except Exception as e:
            logger.error(
                "Failed to check record existence",
                model=self.model.__name__,
                error=str(e)
            )
            return False

    async def filter_by(
        self,
        session: AsyncSession,
        filter_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        load_relations: bool = False
    ) -> List[ModelType]:
        """
        Получить записи по критериям фильтрации.

        Args:
            session: Сессия базы данных
            filter_criteria: Критерии фильтрации
            limit: Максимальное количество записей
            offset: Смещение
            order_by: Поле для сортировки
            load_relations: Загружать ли связанные объекты

        Returns:
            List[ModelType]: Список найденных записей
        """
        try:
            stmt = select(self.model)

            # Добавляем условия фильтрации
            where_conditions = []
            for field_name, field_value in filter_criteria.items():
                field = getattr(self.model, field_name)
                if isinstance(field_value, list):
                    where_conditions.append(field.in_(field_value))
                else:
                    where_conditions.append(field == field_value)

            if where_conditions:
                stmt = stmt.where(and_(*where_conditions))

            # Добавляем сортировку
            if order_by:
                order_field = getattr(self.model, order_by)
                stmt = stmt.order_by(order_field)

            # Добавляем пагинацию
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)

            # Добавляем загрузку связей
            if load_relations:
                stmt = self._add_relationship_loading(stmt)

            result = await session.execute(stmt)
            records = list(result.scalars().all())

            logger.debug(
                "Records filtered",
                model=self.model.__name__,
                count=len(records),
                criteria=filter_criteria
            )

            return records

        except Exception as e:
            logger.error(
                "Failed to filter records",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to filter {self.model.__name__}: {str(e)}")

    async def search(
        self,
        session: AsyncSession,
        search_term: str,
        search_fields: List[str],
        limit: Optional[int] = None
    ) -> List[ModelType]:
        """
        Поиск записей по текстовым полям.

        Args:
            session: Сессия базы данных
            search_term: Поисковый запрос
            search_fields: Поля для поиска
            limit: Максимальное количество результатов

        Returns:
            List[ModelType]: Список найденных записей
        """
        try:
            stmt = select(self.model)

            # Формируем условия поиска
            search_conditions = []
            for field_name in search_fields:
                field = getattr(self.model, field_name)
                search_conditions.append(field.ilike(f"%{search_term}%"))

            if search_conditions:
                stmt = stmt.where(or_(*search_conditions))

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            records = list(result.scalars().all())

            logger.debug(
                "Search completed",
                model=self.model.__name__,
                search_term=search_term,
                results_count=len(records)
            )

            return records

        except Exception as e:
            logger.error(
                "Failed to search records",
                model=self.model.__name__,
                error=str(e)
            )
            raise DatabaseError(f"Failed to search {self.model.__name__}: {str(e)}")

    def _add_relationship_loading(self, stmt):
        """
        Добавить загрузку связанных объектов к запросу.

        Args:
            stmt: SQLAlchemy запрос

        Returns:
            Модифицированный запрос
        """
        # Автоматически определяем все relationships в модели
        relationships = []
        for attr_name in dir(self.model):
            attr = getattr(self.model, attr_name)
            if hasattr(attr, 'property') and hasattr(attr.property, 'mapper'):
                relationships.append(attr_name)

        # Добавляем selectinload для каждой связи
        for rel_name in relationships:
            rel = getattr(self.model, rel_name)
            stmt = stmt.options(selectinload(rel))

        return stmt

    async def get_or_create(
        self,
        session: AsyncSession,
        defaults: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> tuple[ModelType, bool]:
        """
        Получить существующую запись или создать новую.

        Args:
            session: Сессия базы данных
            defaults: Значения по умолчанию для создания
            **kwargs: Критерии поиска

        Returns:
            tuple: (instance, created) - запись и флаг создания
        """
        # Пытаемся найти существующую запись
        where_conditions = []
        for field_name, field_value in kwargs.items():
            field = getattr(self.model, field_name)
            where_conditions.append(field == field_value)

        stmt = select(self.model).where(and_(*where_conditions))
        result = await session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance:
            return instance, False

        # Создаем новую запись
        create_data = kwargs.copy()
        if defaults:
            create_data.update(defaults)

        instance = await self.create(session, **create_data)
        return instance, True