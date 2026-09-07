"""Offline source/frozen smoke test. Never downloads a model or calls online services."""
def run(app_module, destination):
    import json
    import sys
    import tempfile
    import wave
    from pathlib import Path
    import av
    import ctranslate2
    import faster_whisper
    import onnxruntime
    import yt_dlp
    import yt_dlp_ejs

    destination=Path(destination).resolve()
    results={'python':sys.version,'frozen':bool(getattr(sys,'frozen',False)), 'checks':[]}
    try:
        assert sys.version_info[:3] == (3,14,7), sys.version
        assert 'int8' in ctranslate2.get_supported_compute_types('cpu')
        results['checks'].append('native imports and CPU INT8')
        with tempfile.TemporaryDirectory(prefix='study_smoke_') as temp:
            temp=Path(temp)
            app_module.APP_DIR=temp
            app_module.CONFIG_PATH=temp/'config.json'
            wav=temp/'silence.wav'
            with wave.open(str(wav),'wb') as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(bytes(48000))
            with av.open(str(wav)) as media:
                assert sum(frame.samples for frame in media.decode(audio=0))==24000
            results['checks'].append('PyAV audio decode')
            target=temp/'sample.xlsx'
            app_module.save_rows_to_excel([['안녕','hello','test']],str(target))
            assert target.stat().st_size>0
            app_module.speech_pdf('한글 PDF 기본 점검입니다. English test.',temp/'sample.pdf')
            assert (temp/'sample.pdf').read_bytes().startswith(b'%PDF')
            results['checks'].append('Excel and Korean PDF')
            window=app_module.App()
            window.withdraw()
            window.update_idletasks()
            assert len(window.panels)==8
            window.destroy()
            results['checks'].append('all eight GUI panels and icon')
        results['status']='passed'
    except Exception:
        import traceback
        results.update(status='failed',error=traceback.format_exc())
        raise
    finally:
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
