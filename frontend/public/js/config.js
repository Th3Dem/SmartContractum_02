/**
 * Antigravity WYSIWYG Editor - Centralized Publication Configuration
 * Dictionaries for audiences, topics, formats, complexities, and limits.
 * 100% offline-first. Strict Onest font family and no emojis.
 */

(function (window) {
  'use strict';

  const AUDIENCES = [
    {
      id: 'smart-contracts-dev',
      title: 'Разработчики смарт-контрактов',
      description: 'Создание, отладка, оптимизация и архитектура смарт-контрактов'
    },
    {
      id: 'architects-integrators',
      title: 'Архитекторы и интеграторы',
      description: 'Проектирование распределенных систем, интеграция с внешними сервисами'
    },
    {
      id: 'analysts',
      title: 'Аналитики',
      description: 'Системный и бизнес-анализ, формализация требований к логике сделок'
    },
    {
      id: 'qa-engineers',
      title: 'Тестировщики и инженеры качества',
      description: 'Функциональное тестирование, верификация и тест-кейсы смарт-контрактов'
    },
    {
      id: 'security-auditors',
      title: 'Специалисты по ИБ и аудиторы',
      description: 'Аудит безопасности, поиск уязвимостей и защита транзакций'
    },
    {
      id: 'legal-compliance',
      title: 'Юристы и специалисты по комплаенсу',
      description: 'Правовой статус смарт-контрактов, регуляторные требования и комплаенс'
    },
    {
      id: 'data-oracles',
      title: 'Специалисты по данным и оракулам',
      description: 'Поставка доверенных внешних данных, провайдеры оракулов и аналитика'
    },
    {
      id: 'devops-sre',
      title: 'Инженеры эксплуатации и DevOps/SRE',
      description: 'Развертывание узлов, мониторинг, надежность и сопровождение инфраструктуры'
    },
    {
      id: 'product-project-managers',
      title: 'Руководители продуктов и проектов',
      description: 'Управление продуктом, roadmap, метрики эффективности и внедрения'
    },
    {
      id: 'business-users',
      title: 'Бизнес-заказчики и пользователи',
      description: 'Практическая польза, бизнес-сценарии и экономический эффект'
    }
  ];

  const TOPICS = [
    { id: 'pksc-architecture', title: 'Архитектура и развитие ПКСК', description: 'Архитектурные паттерны, консенсус и масштабирование корпоративных систем' },
    { id: 'smart-contracts-development', title: 'Разработка смарт-контрактов', description: 'Написание безопасного кода, оптимизация исполнения и шаблоны контрактов' },
    { id: 'business-logic-deals', title: 'Бизнес-логика и моделирование сделок', description: 'Автоматизация бизнес-процессов, алгоритмы сделок и транзакций' },
    { id: 'testing-and-quality', title: 'Тестирование и качество', description: 'Модульное, интеграционное и нагрузочное тестирование контрактов и узлов' },
    { id: 'information-security', title: 'Информационная безопасность', description: 'Защита узлов, предотвращение атак и безопасность ключей' },
    { id: 'audit-and-verification', title: 'Аудит и проверка смарт-контрактов', description: 'Формальная верификация, статический анализ и аудит безопасности' },
    { id: 'law-and-compliance', title: 'Право и комплаенс', description: 'Правовой статус смарт-контрактов и регуляторные требования РФ' },
    { id: 'oracles-and-data', title: 'Оракулы и доверенные внешние данные', description: 'Поставка доверенных внешних данных и верификация источников' },
    { id: 'integrations-and-api', title: 'Интеграции и API', description: 'Интеграция реестров с банковскими и корпоративными системами' },
    { id: 'digital-ruble-payments', title: 'Цифровой рубль и программируемые расчеты', description: 'Программируемые расчеты, интеграция цифрового рубля и платежи' },
    { id: 'lifecycle-versioning', title: 'Жизненный цикл и версии смарт-контрактов', description: 'Управление версиями контрактов и обновление логики' },
    { id: 'infrastructure-operations', title: 'Инфраструктура и эксплуатация', description: 'Развертывание узлов, мониторинг и сопровождение сетей' },
    { id: 'business-cases-adoption', title: 'Бизнес-сценарии и внедрение', description: 'Практические кейсы внедрения распределенных реестров' }
  ];

  const FORMATS = [
    {
      id: 'tutorial',
      title: 'Туториал',
      description: 'Пошаговое практическое руководство по решению конкретной задачи'
    },
    {
      id: 'retrospective',
      title: 'Ретроспектива',
      description: 'Разбор завершенного проекта, выводы, ошибки и извлеченные уроки'
    },
    {
      id: 'opinion',
      title: 'Мнение',
      description: 'Авторский взгляд на тренды, спорные вопросы и развитие технологий'
    },
    {
      id: 'interview',
      title: 'Интервью',
      description: 'Беседа с экспертом отрасли, разработчиком или участником команды'
    },
    {
      id: 'reportage',
      title: 'Репортаж',
      description: 'Освещение отраслевого события, хакатона, конференции или релиза'
    },
    {
      id: 'case-study',
      title: 'Кейс',
      description: 'Реальный пример внедрения решения с описанием результатов и метрик'
    },
    {
      id: 'roadmap',
      title: 'Roadmap',
      description: 'Стратегический план развития технологии, архитектуры или продукта'
    },
    {
      id: 'review',
      title: 'Обзор',
      description: 'Сравнительный анализ инструментов, библиотек, фреймворков или подходов'
    },
    {
      id: 'faq',
      title: 'FAQ',
      description: 'Ответы на часто задаваемые вопросы с практическими пояснениями'
    },
    {
      id: 'digest',
      title: 'Дайджест',
      description: 'Тематическая подборка актуальных новостей, статей и материалов'
    },
    {
      id: 'analytics',
      title: 'Аналитика',
      description: 'Глубокое исследование рынка, статистических данных или стека технологий'
    },
    {
      id: 'news',
      title: 'Новость',
      description: 'Оперативное сообщение о событии, релизе или изменении в индустрии'
    },
    {
      id: 'note',
      title: 'Заметка',
      description: 'Краткая мысль, наблюдение или быстрый практический совет'
    }
  ];

  const COMPLEXITIES = [];

  const COVER = {
    REQUIRED: false,
    ALLOWED_FORMATS: ['image/jpeg', 'image/png', 'image/webp', 'image/gif'],
    ALLOWED_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.webp', '.gif'],
    MAX_FILE_BYTES: 10 * 1024 * 1024, // 10 МБ
    TARGET_WIDTH: 780,
    TARGET_HEIGHT: 350,
    ASPECT_RATIO_W: 78,
    ASPECT_RATIO_H: 35,
    ASPECT_RATIO_VALUE: 780 / 350, // ~2.22857
    ASPECT_RATIO_STR: '780 / 350',
    FEED_FULL_WIDTH: true,
    FEED_MAX_WIDTH: '100%'
  };

  const MATERIAL_TYPES = [
    { id: 'publication', title: 'Публикации', singular: 'Публикация' },
    { id: 'question', title: 'Вопросы', singular: 'Вопрос' }
  ];
  MATERIAL_TYPES.publication = 'Публикации';
  MATERIAL_TYPES.question = 'Вопросы';
  // Backward-compatible read mappings
  MATERIAL_TYPES.article = 'Публикации';
  MATERIAL_TYPES.post = 'Публикации';
  MATERIAL_TYPES.news = 'Публикации';

  const DEFAULT_FEED_SETTINGS = {
    materialTypes: ['publication', 'question'],
    complexityLevels: []
  };

  const LIMITS = {
    KEYWORDS_MIN: 1,
    KEYWORDS_MAX: 10,
    KEYWORD_MAX_LEN: 60,
    TOPICS_MIN: 1,
    TOPICS_MAX: 5,
    DESCRIPTION_MIN: 50,
    DESCRIPTION_MAX: 500,
    COVER_MAX_BYTES: 10 * 1024 * 1024, // 10MB
    COVER_WIDTH: 780,
    COVER_HEIGHT: 350
  };

  const PublicationConfig = {
    AUDIENCES,
    TOPICS,
    FORMATS,
    COMPLEXITIES,
    MATERIAL_TYPES,
    DEFAULT_FEED_SETTINGS,
    LIMITS,
    COVER,

    getMaterialTypeById(id) {
      if (id === 'article' || id === 'post' || id === 'news') {
        id = 'publication';
      }
      return MATERIAL_TYPES.find(m => m.id === id) || null;
    },

    getAudienceById(id) {
      return AUDIENCES.find(a => a.id === id) || null;
    },

    getTopicById(id) {
      return TOPICS.find(t => t.id === id) || null;
    },

    getFormatById(id) {
      return FORMATS.find(f => f.id === id) || null;
    },

    getComplexityById(id) {
      return COMPLEXITIES.find(c => c.id === id) || null;
    }
  };

  window.PublicationConfig = PublicationConfig;
  window.MATERIAL_TYPES = MATERIAL_TYPES;
  window.DEFAULT_FEED_SETTINGS = DEFAULT_FEED_SETTINGS;

})(window);
