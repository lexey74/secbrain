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
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        Инициализация Whisper модели
        
        Args:
            model_size: Размер модели (tiny, base, small, medium, large)
            device: Устройство (cpu, cuda)
        """
        self.model_size = model_size
        self.device = device
        self.model = None
    
    def load_model(self) -> None:
        """Ленивая загрузка модели"""
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
                
                print(f"🔄 Загрузка Whisper модели ({self.model_size})...")
                print(f"   ⏳ Это может занять некоторое время при первом запуске...")
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type="int8"
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
        
        # Запуск транскрибации
        segments, info = self.model.transcribe(
            str(media_path),
            language="ru",  # Можно сделать auto-detect
            beam_size=5,
            vad_filter=True  # Фильтрация тишины
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
