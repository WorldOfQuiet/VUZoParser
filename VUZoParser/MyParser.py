import requests
from bs4 import BeautifulSoup
from lxml import html, etree
import os
import time
from selenium.webdriver.common.by import By
from tqdm import tqdm
from collections import deque
import sqlite3
from typing import List, Dict, Any
import undetected_chromedriver as uc
from fake_useragent import UserAgent

timeout = 0.1


class MyBrowser:
    def __init__(self):
        self.user_agent = UserAgent().random

        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={self.user_agent}")

        self.driver = uc.Chrome(
            options=options,
            user_data_dir=os.path.abspath('chromedriver-linux64')
        )

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print('Browser init successful')

    def restart_browser(self):
        try:
            self.driver.quit()
        except Exception as e:
            print(f"Error closing driver: {e}")

        time.sleep(2)

        self.__init__()

    def click_to_element(self, class_names: str = None, xpath: str = None):
        if xpath:
            elements = self.driver.find_elements(By.XPATH, xpath)
        elif class_names:
            page_css_selector = '.' + '.'.join(class_names.split())
            elements = self.driver.find_elements(By.CSS_SELECTOR, page_css_selector)
        else:
            raise ValueError("Either class_names or xpath must be provided")

        for element in elements:
            element.click()
            time.sleep(timeout)



class MyParser:
    @classmethod
    def get_target_class(cls, class_name_list: list, target_type: str, html_text: str):
        data_page = BeautifulSoup(html_text, "html.parser").find_all(target_type)

        target_data_page = []
        for item in data_page:
            try:
                if all(name in item['class'] for name in class_name_list): target_data_page += [item]
            except KeyError:
                pass

        return [item for item in target_data_page]

    @classmethod
    def int_normalization(cls, s: str):
        try: return int(s)
        except ValueError: return None

    @classmethod
    def str_normalization(cls, s: str):
        if s[0] == ' ': s = s[1:]
        if s[-1] == ' ': s = s[:-1]
        return s

    @classmethod
    def get_page_element(cls, html_page: str, xpath: str):
        page = html.fromstring(html_page)
        return page.xpath(xpath)

    def __init__(self):
        self.browser = MyBrowser()

    def get_educational_program_links_from_direction(self, url: str):
        forms_links = [url]+['https:' + x.attrib['href'] for x in html.fromstring(requests.get(url).content).xpath('//*[@id="content"]/div[5]/div[2]/ul/li/a')]

        program_links = []
        for form_link in forms_links:
            self.browser.driver.get(form_link)
            time.sleep(timeout)
            while True:
                self.browser.click_to_element(class_names='tick-spoiler-1-trigger more-specialities-trigger plus link-like')
                program_links += ['https:'+x.attrs['href'] for x in self.get_target_class(['button-1'], 'a', self.browser.driver.page_source)]

                try: next_button = self.get_page_element(self.browser.driver.page_source, '//*[@id="pagination-wrapper"]/div[1]/a')[-1]
                except IndexError: break
                if 'сюда' in next_button.text: self.browser.driver.get('https:' + next_button.attrib['href'])
                else: break
        return program_links

    def get_direction_links_from_main_page(self, main_url):
        self.browser.driver.get(main_url)
        time.sleep(timeout*10)

        self.browser.click_to_element(xpath='//*[@id="by-specialities-more-0"]/div[1]')
        self.browser.click_to_element(class_names='tick-spoiler-3-links by-specialities-spoiler-links')

        return ['https:' + x for x in [x.contents[1].get('href') for x in self.get_target_class(['speciality-full'], 'div', self.browser.driver.page_source)] if x is not None]

    def get_institute_information_from_institute_page(self, url: str):
        html_page = requests.get(url).content
        page = html.fromstring(html_page)

        speciality_full = [x.contents for x in self.get_target_class([], 'span', etree.tostring(page.xpath('//*[@id="content"]/div[2]/div[2]/div/div[2]/div[1]/div[2]/ul/li[1]/div')[0]))]

        if ['отделение'] in speciality_full: branch_ege_index = speciality_full.index(['отделение'])
        elif ['егэ'] in speciality_full: branch_ege_index = speciality_full.index(['егэ'])
        else: branch_ege_index = 0


        return {
            'institute_name': self.get_target_class(['institute-search-title', 'h3', 'color-l0'], 'a', html_page)[0].contents[0],
            'direction': speciality_full[2][0],
            'program_names': [self.str_normalization(x[0]) for x in speciality_full[4: branch_ege_index]],
            'form': self.str_normalization(speciality_full[-2][0]),
            'history': [{
                'year': self.int_normalization(page.xpath(f'//*[@id="content"]/div[4]/div[2]/ul/li/ul/li[{i + 1}]/div/div[1]/span')[0].text[:4]),
                'budget_places': self.int_normalization(page.xpath(f'//*[@id="content"]/div[4]/div[2]/ul/li/ul/li[{i + 1}]/div/div[2]/text()[1]')[0]),
                'paid_places/contract': self.int_normalization(page.xpath(f'//*[@id="content"]/div[4]/div[2]/ul/li/ul/li[{i + 1}]/div/div[2]/text()[2]')[0]),
                'passing_score_budget': self.int_normalization(page.xpath(f'//*[@id="content"]/div[4]/div[2]/ul/li/ul/li[{i + 1}]/div/div[4]/text()[1]')[0]),
                'passing_score_paid': self.int_normalization(page.xpath(f'//*[@id="content"]/div[4]/div[2]/ul/li/ul/li[{i + 1}]/div/div[4]/text()[2]')[0])
            } for i in range(4)],
            'required_exams': ['/'.join(self.str_normalization(item) for item in x if isinstance(item, str)) for x in speciality_full[speciality_full.index(['егэ']) + 1: -2] if len(x[0]) > 1 and x[0] != 'или'] if ['егэ'] in speciality_full else []
        }


class SmoothTQDM(tqdm):
    def __init__(self, *args, **kwargs):
        # Количество последних итераций для усреднения (по умолчанию 10)
        self.smooth_window = kwargs.pop('smooth_window', 10)
        super().__init__(*args, **kwargs)

        # Очередь для хранения времени последних итераций
        self._time_history = deque(maxlen=self.smooth_window)
        self._last_time = time.time()

    def update(self, n=1):
        # Защита от отсутствия _time_history
        if not hasattr(self, '_time_history'):
            self._time_history = deque(maxlen=self.smooth_window)

        # Вычисляем время текущей итерации
        current_time = time.time()
        iter_time = current_time - self._last_time
        self._last_time = current_time

        # Добавляем в историю (время на одну итерацию)
        if n > 0:
            time_per_item = iter_time / n
            self._time_history.append(time_per_item)

        # Вызываем родительский update
        super().update(n)

    @property
    def format_dict(self):
        # Получаем формат от родителя
        d = super().format_dict

        # Защита от отсутствия _time_history
        if hasattr(self, '_time_history') and self._time_history:
            # Рассчитываем среднее время итерации
            avg_iter_time = sum(self._time_history) / len(self._time_history)

            # Обновляем значения
            if avg_iter_time > 0:
                d['rate'] = 1.0 / avg_iter_time

            if self.total and d.get('rate'):
                d['remaining'] = (self.total - self.n) / d['rate']

        return d


class UniversityDB:
    def __init__(self, db_name: str = "university.db"):
        self.db_name = db_name

    def __enter__(self):
        """Вызывается при входе в контекстный менеджер"""
        self.conn = sqlite3.connect(self.db_name)

        # Регистрируем пользовательскую функцию LOWER для Unicode
        def unicode_lower(s):
            return s.lower() if s is not None else s

        self.conn.create_function("LOWER", 1, unicode_lower)

        self.cursor = self.conn.cursor()
        self.create_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Вызывается при выходе из контекстного менеджера"""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def create_tables(self):
        """Создание нормализованной структуры таблиц с индексами"""
        # Учебные заведения
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS institutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        ''')

        # Направления подготовки (многие-ко-многим)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS directions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        ''')

        # Формы обучения (динамические)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS education_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form TEXT UNIQUE
            )
        ''')

        # Названия программ
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        ''')

        # Экзамены
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        ''')

        # Основная таблица образовательных программ
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS education_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institute_id INTEGER,
                direction_id INTEGER,
                education_form_id INTEGER,
                FOREIGN KEY (institute_id) REFERENCES institutes(id),
                FOREIGN KEY (direction_id) REFERENCES directions(id),
                FOREIGN KEY (education_form_id) REFERENCES education_forms(id),
                UNIQUE(institute_id, direction_id, education_form_id)
            )
        ''')

        # Связь программ с названиями (многие-ко-многим)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_program_names (
                program_id INTEGER,
                program_name_id INTEGER,
                FOREIGN KEY (program_id) REFERENCES education_programs(id),
                FOREIGN KEY (program_name_id) REFERENCES program_names(id),
                PRIMARY KEY (program_id, program_name_id)
            )
        ''')

        # Связь программ с экзаменами (многие-ко-многим)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_exams (
                program_id INTEGER,
                exam_id INTEGER,
                FOREIGN KEY (program_id) REFERENCES education_programs(id),
                FOREIGN KEY (exam_id) REFERENCES exams(id),
                PRIMARY KEY (program_id, exam_id)
            )
        ''')

        # История приема
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admission_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                year INTEGER,
                budget_places INTEGER,
                paid_places_contract INTEGER,
                passing_score_budget INTEGER,
                passing_score_paid INTEGER,
                FOREIGN KEY (program_id) REFERENCES education_programs(id),
                UNIQUE(program_id, year)
            )
        ''')

        # ДОБАВЛЕНЫ ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_education_programs_institute 
            ON education_programs(institute_id)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_education_programs_direction 
            ON education_programs(direction_id)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_education_programs_composite 
            ON education_programs(institute_id, direction_id, education_form_id)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_admission_history_program_year 
            ON admission_history(program_id, year)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_program_names_name 
            ON program_names(name)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_program_program_names_program 
            ON program_program_names(program_id)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_program_exams_program 
            ON program_exams(program_id)
        ''')

        # Включаем поддержку внешних ключей
        self.cursor.execute('PRAGMA foreign_keys = ON')

        self.conn.commit()

    def _get_or_create_id(self, table: str, name: str) -> int:
        """Получает ID значения или создает новую запись"""
        # Определяем имя столбца в зависимости от таблицы
        if table == 'education_forms':
            column = 'form'
        else:
            column = 'name'

        self.cursor.execute(f"SELECT id FROM {table} WHERE {column} = ?", (name,))
        result = self.cursor.fetchone()

        if result:
            return result[0]
        else:
            self.cursor.execute(f"INSERT INTO {table} ({column}) VALUES (?)", (name,))
            return self.cursor.lastrowid

    def insert_record(self, record: Dict[str, Any]) -> int:
        """Вставка записи с улучшенной целостностью данных"""
        # Включаем поддержку внешних ключей
        self.cursor.execute('PRAGMA foreign_keys = ON')

        try:
            # Получаем или создаем ID для основных сущностей
            institute_id = self._get_or_create_id('institutes', record['institute_name'])
            direction_id = self._get_or_create_id('directions', record['direction'])
            form_id = self._get_or_create_id('education_forms', record['form'])

            # Создаем или находим программу
            self.cursor.execute('''
                INSERT OR IGNORE INTO education_programs 
                (institute_id, direction_id, education_form_id) 
                VALUES (?, ?, ?)
            ''', (institute_id, direction_id, form_id))

            # НАДЕЖНОЕ получение ID программы
            self.cursor.execute('''
                SELECT id FROM education_programs 
                WHERE institute_id = ? AND direction_id = ? AND education_form_id = ?
            ''', (institute_id, direction_id, form_id))

            result = self.cursor.fetchone()
            if not result:
                raise ValueError("Failed to create or find education program")

            program_id = result[0]

            # Добавляем названия программ
            for program_name in record['program_names']:
                program_name_id = self._get_or_create_id('program_names', program_name)
                self.cursor.execute('''
                    INSERT OR IGNORE INTO program_program_names 
                    (program_id, program_name_id) VALUES (?, ?)
                ''', (program_id, program_name_id))

            # Добавляем экзамены
            for exam in record['required_exams']:
                exam_id = self._get_or_create_id('exams', exam)
                self.cursor.execute('''
                    INSERT OR IGNORE INTO program_exams 
                    (program_id, exam_id) VALUES (?, ?)
                ''', (program_id, exam_id))

            # Добавляем историю приема
            for year_data in record['history']:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO admission_history 
                    (program_id, year, budget_places, paid_places_contract, 
                     passing_score_budget, passing_score_paid) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    program_id,
                    year_data['year'],
                    year_data['budget_places'],
                    year_data.get('paid_places/contract'),
                    year_data['passing_score_budget'],
                    year_data['passing_score_paid']
                ))

            # КОММИТ ТОЛЬКО ПРИ УСПЕШНОМ ВЫПОЛНЕНИИ ВСЕХ ОПЕРАЦИЙ
            return program_id

        except Exception as e:
            # Откатываем транзакцию при ошибке
            self.conn.rollback()
            raise e

    def get_records(self, search_criteria: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Поиск записей с улучшенной производительностью - устранение N+1"""
        if search_criteria is None:
            search_criteria = {}

        # ОДИН запрос для получения всех данных (кроме истории)
        query = '''
            SELECT 
                i.name as institute_name,
                d.name as direction,
                ef.form as education_form,
                ep.id as program_id,
                GROUP_CONCAT(DISTINCT pn.name) as program_names_list,
                GROUP_CONCAT(DISTINCT e.name) as exams_list
            FROM education_programs ep
            JOIN institutes i ON ep.institute_id = i.id
            JOIN directions d ON ep.direction_id = d.id
            JOIN education_forms ef ON ep.education_form_id = ef.id
            LEFT JOIN program_program_names ppn ON ep.id = ppn.program_id
            LEFT JOIN program_names pn ON ppn.program_name_id = pn.id
            LEFT JOIN program_exams pe ON ep.id = pe.program_id
            LEFT JOIN exams e ON pe.exam_id = e.id
            WHERE 1=1
        '''
        params = []

        # Добавляем условия поиска (ПОИСК БЕЗ УЧЕТА РЕГИСТРА с использованием LOWER)
        for field, value in search_criteria.items():
            if field == 'institute_name':
                query += " AND LOWER(i.name) LIKE LOWER(?)"
                params.append(f'%{value}%')
            elif field == 'direction':
                query += " AND LOWER(d.name) LIKE LOWER(?)"
                params.append(f'%{value}%')
            elif field == 'form':
                query += " AND LOWER(ef.form) LIKE LOWER(?)"
                params.append(f'%{value}%')
            elif field == 'program_names':
                query += ''' AND ep.id IN (
                    SELECT ppn.program_id 
                    FROM program_program_names ppn 
                    JOIN program_names pn ON ppn.program_name_id = pn.id 
                    WHERE LOWER(pn.name) LIKE LOWER(?)
                )'''
                params.append(f'%{value}%')
            elif field == 'required_exams':
                query += ''' AND ep.id IN (
                    SELECT pe.program_id 
                    FROM program_exams pe 
                    JOIN exams e ON pe.exam_id = e.id 
                    WHERE LOWER(e.name) LIKE LOWER(?)
                )'''
                params.append(f'%{value}%')

        query += " GROUP BY ep.id"  # Группируем по программе

        self.cursor.execute(query, params)
        programs = self.cursor.fetchall()

        result = []
        for program in programs:
            program_id = program[3]
            full_record = {
                'institute_name': program[0],
                'direction': program[1],
                'form': program[2],
                'program_names': program[4].split(',') if program[4] else [],
                'history': self._get_history(program_id),
                'required_exams': program[5].split(',') if program[5] else []
            }
            result.append(full_record)

        return result

    def _get_program_names(self, program_id: int) -> List[str]:
        """Получает названия программ для конкретной программы"""
        self.cursor.execute('''
            SELECT pn.name 
            FROM program_names pn
            JOIN program_program_names ppn ON pn.id = ppn.program_name_id
            WHERE ppn.program_id = ?
        ''', (program_id,))
        return [row[0] for row in self.cursor.fetchall()]

    def _get_history(self, program_id: int) -> List[Dict[str, Any]]:
        """Получает историю приема для программы"""
        self.cursor.execute('''
            SELECT year, budget_places, paid_places_contract, 
                   passing_score_budget, passing_score_paid
            FROM admission_history
            WHERE program_id = ?
            ORDER BY year DESC
        ''', (program_id,))

        history = []
        for row in self.cursor.fetchall():
            history.append({
                'year': row[0],
                'budget_places': row[1],
                'paid_places/contract': row[2],
                'passing_score_budget': row[3],
                'passing_score_paid': row[4]
            })
        return history

    def _get_required_exams(self, program_id: int) -> List[str]:
        """Получает требуемые экзамены для программы"""
        self.cursor.execute('''
            SELECT e.name 
            FROM exams e
            JOIN program_exams pe ON e.id = pe.exam_id
            WHERE pe.program_id = ?
        ''', (program_id,))
        return [row[0] for row in self.cursor.fetchall()]

    def clear_database(self):
        """Очистка всей базы данных с учетом целостности"""
        # Включаем поддержку внешних ключей
        self.cursor.execute('PRAGMA foreign_keys = ON')

        # Правильный порядок удаления (сначала дочерние таблицы)
        tables = [
            'admission_history',
            'program_exams',
            'program_program_names',
            'education_programs',
            'exams',
            'program_names',
            'education_forms',
            'directions',
            'institutes'
        ]

        for table in tables:
            self.cursor.execute(f"DELETE FROM {table}")

        # Сбрасываем автоинкременты
        for table in tables:
            if table not in ['admission_history', 'program_exams', 'program_program_names']:
                self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = ?", (table,))

        self.conn.commit()
