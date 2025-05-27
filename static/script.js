document.addEventListener('DOMContentLoaded', () => {
    // Находим наши основные элементы
    const burger = document.getElementById('burger-menu');
    const nav = document.getElementById('main-nav');

    // Убеждаемся, что они существуют, чтобы не было ошибок
    if (burger && nav) {
        // Вешаем "прослушку" на клик по бургеру для открытия/закрытия меню
        burger.addEventListener('click', () => {
            nav.classList.toggle('is-open');
            burger.classList.toggle('is-open');
        });

        // --- НАЧАЛО НОВОГО КОДА ---

        // Находим ВСЕ ссылки внутри навигации
        const navLinks = nav.querySelectorAll('a');

        // Перебираем каждую ссылку
        navLinks.forEach(link => {
            // И вешаем "прослушку" на клик по каждой из них
            link.addEventListener('click', () => {
                // Если меню открыто (содержит класс 'is-open')
                if (nav.classList.contains('is-open')) {
                    // То мы удаляем классы, чтобы его закрыть
                    nav.classList.remove('is-open');
                    burger.classList.remove('is-open');
                }
            });
        });

        // --- КОНЕЦ НОВОГО КОДА ---
    }
});