MCP — Multi-Component Processor for React

MCP — агент для генерации React (TypeScript/TSX) компонентов на основе Figma макетов и локальной React дизайн-системы. Он автоматически сопоставляет элементы макета с компонентами вашей дизайн-системы и генерирует production-ready код.

Основные возможности

Генерация компонентов React из Figma макета.

Использование локальной дизайн-системы с реальными props и стилями.

Автоматическая генерация интерфейсов пропсов.

Inline-стили для отсутствующих компонентов.

Поддержка современных React-паттернов: функциональные компоненты, хуки.

Форматирование кода по стандартам Prettier / ESLint.

Документирование ключевых частей кода комментариями.

Гибкая интеграция в существующие проекты и CI/CD пайплайны.

Сценарий использования

Получаем JSON макета Figma через функцию export_figma_layout(file_key, frame_name?).

Сканируем локальную дизайн-систему через scan_design_system(directory_path).

Генерируем TSX компонент:

Используем готовые компоненты из дизайн-системы.

Для отсутствующих компонентов создаём с inline-стилями.

Автоматически создаём интерфейс Props.

Результат — production-ready TSX компонент, готовый к использованию.

Пример сгенерированного компонента
import { Card, Avatar, Text, Button, Stack } from '@your-design-system/core';

interface UserCardProps {
  avatarSrc: string;
  avatarAlt?: string;
  name: string;
  email: string;
  onEdit?: () => void;
  onDelete?: () => void;
}

export const UserCard = ({ avatarSrc, avatarAlt = '', name, email, onEdit, onDelete }: UserCardProps) => {
  return (
    <Card className="w-full max-w-sm">
      <Stack spacing="md" align="center">
        <Avatar src={avatarSrc} alt={avatarAlt} size={80} />
        <Text as="h2" variant="heading" size="lg" className="text-center">{name}</Text>
        <Text as="p" variant="body" color="secondary" className="text-center">{email}</Text>
        <Stack direction="horizontal" spacing="sm" justify="center" align="center">
          <Button variant="primary" size="md" onClick={onEdit} disabled={!onEdit}>Редактировать</Button>
          <Button variant="danger" size="md" onClick={onDelete} disabled={!onDelete}>Удалить</Button>
        </Stack>
      </Stack>
    </Card>
  );
};

Метрики эффективности

Время генерации компонентов.

Соответствие макету (процент совпадения слоев Figma и компонентов).

Качество кода (lint, форматирование).

Повторное использование компонентов.

Снижение багов UI после генерации.

Исполнители

MCP агент (OpenAI/GPT-OSS-20B)

Функции: export_figma_layout, scan_design_system

React разработчики / UX дизайнеры

Бизнес-пользователи

Frontend разработчики

UI/UX дизайнеры

Product-менеджеры

QA инженеры

Будущее развитие

Автоматическая генерация тестов для компонентов.

Поддержка Storybook и визуальной проверки компонентов.

Расширение базы компонентов дизайн-системы.

Ускорение обработки больших макетов через многопоточность.

Генерация интерактивных элементов: формы, таблицы, модальные окна.

Конфигурация .env
# Figma Configuration
FIGMA_ACCESS_TOKEN=figd_LIFJ11-FuEbz7t2Txtr_KXRFuF25RFlfDI8RebJX
FIGMA_API_BASE_URL=https://api.figma.com/v1

# Server Configuration
PORT=8000
LOG_LEVEL=INFO
HOST=0.0.0.0

# Design System Configuration
DS_SCAN_MAX_DEPTH=10
DS_SUPPORTED_EXTENSIONS=.tsx,.ts,.jsx,.js

# API Limits
FIGMA_REQUEST_TIMEOUT=30

Быстрый старт

Клонируйте репозиторий: git clone https://github.com/your-org/mcp.git && cd mcp

Установите зависимости: npm install

Настройте .env файл (Figma токен и путь к дизайн-системе)

Запустите сервер: npm start

Отправляйте запросы на генерацию компонентов через MCP API
