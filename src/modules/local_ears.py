"""
LocalEars - Транскрибация видео через faster-whisper
"""
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class TranscriptResult:
    """Результат транскрибации"""
    timed_transcript: str  # С таймкодами [MM:SS]
    full_text: str         # Чистый текст
    language: str = "ru"
    duration: float = 0.0


class LocalEars:
    """Локальная транскрибация аудио/видео"""
    
    def __init__(
        self, 
        model_size: str = "base", 
        device: str = "cpu", 
        num_threads: int = 8,
        compute_type: str = "int8"
    ):
        """
        Инициализация Whisper модели
        
        Args:
            model_size: Размер модели (tiny, base, small, medium, large-v2, large-v3)
                       Рекомендации для русского:
                       - small: хороший баланс скорость/точность (244M параметров)
                       - medium: высокая точность (769M параметров)
                       - large-v3: максимальная точность (1550M параметров)
            device: Устройство (cpu, cuda)
            num_threads: Количество потоков для CPU
            compute_type: Тип вычислений (int8, float16, float32)
                         int8 - быстро, средняя точность
                         float16 - медленнее, лучше точность
                         float32 - самое медленное, максимальная точность
        """
        self.model_size = model_size
        self.device = device
        self.num_threads = num_threads
        self.compute_type = compute_type
        self.model = None
    
    def load_model(self) -> None:
        """Ленивая загрузка модели"""
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
                
                print(f"🔄 Загрузка Whisper модели ({self.model_size}, {self.compute_type})...")
                print(f"   ⏳ Это может занять некоторое время при первом запуске...")
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.num_threads
                )
                print("   ✅ Модель Whisper готова")
                
            except ImportError:
                raise ImportError(
                    "Библиотека faster-whisper не установлена. "
                    "Установите: pip install faster-whisper"
                )
    
    def transcribe(self, media_path: Path) -> Optional[TranscriptResult]:
        """
        Транскрибация медиафайла
        
        Args:
            media_path: Путь к видео/аудио файлу
            
        Returns:
            TranscriptResult или None если не видео
        """
        if not media_path or not media_path.exists():
            return None
        
        # Проверяем, что это видео
        if media_path.suffix.lower() not in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
            print("ℹ️  Это изображение, транскрибация не требуется")
            return None
        
        self.load_model()
        
        print("🎤 Транскрибация аудиодорожки...")
        print("   ⏳ Обработка...")
        
        # Запуск транскрибации с улучшенными параметрами
        segments, info = self.model.transcribe(
            str(media_path),
            language="ru",  # Можно изменить на None для auto-detect
            beam_size=10,   # Увеличено с 5 до 10 для лучшей точности
            best_of=5,      # Выбор лучшего из 5 вариантов
            temperature=0.0,  # Детерминированный вывод
            vad_filter=True,  # Фильтрация тишины
            vad_parameters=dict(
                threshold=0.5,
                min_speech_duration_ms=250,
                max_speech_duration_s=float('inf'),
                min_silence_duration_ms=2000,
                speech_pad_ms=400
            ),
            # Начальный промпт для контекста (помогает с русским языком)
            initial_prompt="Транскрипция видео на русском языке из Instagram. "
                          "Включает разговорную речь, сленг, упоминания технологий и социальных сетей."
        )
        
        # Формирование результатов
        timed_lines = []
        full_lines = []
        segment_count = 0
        
        for segment in segments:
            timestamp = self._format_timestamp(segment.start)
            text = segment.text.strip()
            
            timed_lines.append(f"[{timestamp}] {text}")
            full_lines.append(text)
            
            segment_count += 1
            if segment_count % 10 == 0:
                print(f"   📝 Обработано сегментов: {segment_count}")
        
        print(f"   ✅ Транскрибация завершена ({segment_count} сегментов)")
        
        return TranscriptResult(
            timed_transcript="\n".join(timed_lines),
            full_text=" ".join(full_lines),
            language=info.language,
            duration=info.duration
        )
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Форматирование таймкода MM:SS
        
        Args:
            seconds: Время в секундах
            
        Returns:
            Строка вида "03:45"
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
