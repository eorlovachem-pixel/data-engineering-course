import pandas as pd  # Импорт модуля

def load_and_preview():
    """Функция чтения датасета и вывода первых 10 строк."""
    try:
        # Чтение CSV-файла (предполагается, что он лежит в корне проекта)
        df = pd.read_csv('urban_environment_monitoring.csv')
        print("Первые 10 строк датасета:")
        print(df.head(10))
    except FileNotFoundError:
        print("Ошибка: Файл urban_environment_monitoring.csv не найден.")
        print("Убедитесь, что вы сгенерировали его с помощью scripts/generate_dataset.py")

if __name__ == '__main__':  # Инструкция запуска
    load_and_preview()
