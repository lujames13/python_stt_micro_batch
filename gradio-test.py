import gradio as gr
from transcribe_server import TranscriptionServer
import argparse
import uuid
import pylru
import logging
import asyncio

FORMAT = '%(levelname)s: %(asctime)s: %(message)s'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('GradioTest')

CACHE_SIZE = 100
transcription_server_cache = pylru.lrucache(CACHE_SIZE)
transcription_result_cache = pylru.lrucache(CACHE_SIZE)
translation_cache = pylru.lrucache(CACHE_SIZE)  # Cache for translated content

async def transcribe_and_translate_chunks_async(uuid_value, new_chunk, source_language="Chinese (Simplified, China)", target_language="Japanese (Japan)"):
    """Process audio chunk and return transcription and translation."""
    
    # Safety check - if UUID is empty or doesn't exist in cache, don't process
    if not uuid_value or uuid_value not in transcription_server_cache:
        logger.warning(f"Invalid UUID: {uuid_value} or not found in cache")
        return uuid_value, "", ""

    # Get language codes from the language names
    source_lang_code = language_mappings[source_language]
    target_lang_code = language_mappings[target_language]
    
    # Check if translation cache exists for this combination
    translation_key = f"{uuid_value}_{source_lang_code}_{target_lang_code}"
    
    try:
        # Process the audio through the transcription server
        transcript_result_task = asyncio.create_task(
            transcription_server_cache[uuid_value].recv_audio(
                new_chunk=new_chunk,
                language_code=source_lang_code
            )
        )
        transcript_stream_response = await transcript_result_task
        
        # Process transcription results
        history_transcript_results = transcription_result_cache.get(uuid_value, [])
        
        # Remove the last non-final result if it exists
        if len(history_transcript_results) > 0 and not history_transcript_results[len(history_transcript_results)-1].is_final:
            history_transcript_results = history_transcript_results[0:len(history_transcript_results)-1]
        
        # Process new results
        if transcript_stream_response is not None and transcript_stream_response.results and transcript_stream_response.results[0].alternatives:
            speech_event_offset = transcript_stream_response.speech_event_offset
            results = transcript_stream_response.results
            for result in results:
                history_transcript_results.append(result)
        
        transcription_result_cache[uuid_value] = history_transcript_results
        
        # Build the transcript text
        current_transcript = ""
        for result in history_transcript_results:
            if result.alternatives and result.alternatives[0].transcript:
                current_transcript = current_transcript + result.alternatives[0].transcript + ("\n" if result.is_final else "")
        
        # Handle translation
        translated_text = ""
        if current_transcript.strip():
            # Check if we need to translate or can use cached translation
            cached_translation = translation_cache.get(translation_key, "")
            
            if not cached_translation or len(current_transcript) > len(cached_translation.split("|||")[0]):
                # Need to translate or update translation
                translation_task = asyncio.create_task(
                    transcription_server_cache[uuid_value].translate_text(
                        current_transcript,
                        source_lang_code,
                        target_lang_code
                    )
                )
                translated_text = await translation_task
                
                # Cache the translation with the original text for comparison
                translation_cache[translation_key] = f"{current_transcript}|||{translated_text}"
            else:
                # Use cached translation
                translated_text = cached_translation.split("|||")[1]
        
        return uuid_value, current_transcript, translated_text
    
    except Exception as e:
        logger.error(f"Error in transcribe_and_translate_chunks_async: {e}")
        return uuid_value, "", ""

def generate_uuid():
    """Generate a unique UUID for the session."""
    uuid_value = str(uuid.uuid4())
    logger.info(f"Generated UUID = {uuid_value}")
    return uuid_value

def initialize_session():
    """Initialize a new session with UUID and transcription server."""
    session_uuid = generate_uuid()
    transcription_server_cache[session_uuid] = TranscriptionServer(project_id=PROJECT_ID, location=LOCATION, recognizer="-")
    return session_uuid

def start_recording(uuid_value, audio_data, source_language="Chinese (Simplified, China)", target_language="Japanese (Japan)"):
    """Called when recording starts."""
    logger.info(f"Start recording with UUID = {uuid_value}")
    
    # If UUID is empty or invalid, initialize a new one
    if not uuid_value or uuid_value not in transcription_server_cache:
        uuid_value = initialize_session()
        logger.info(f"Initialized new session with UUID = {uuid_value}")
    
    # Clear any cached translations for this UUID
    for key in list(translation_cache.keys()):
        if key.startswith(uuid_value):
            del translation_cache[key]
            
    return uuid_value, "", ""  # Return empty strings for both transcript and translation

def stop_recording(uuid_value, audio_data, source_language="Chinese (Simplified, China)", target_language="Japanese (Japan)"):
    """Called when recording stops."""
    logger.info(f"Stop recording with UUID = {uuid_value}")
    return uuid_value, "", ""

# Language configurations
language_codes = [
    "en-US",  # English (United States)
    "zh-Hans-CN",  # Chinese (Simplified, China)
    "ja-JP",  # Japanese (Japan)
    "de-DE",  # German (Germany)
    "fr-FR",  # French (France)
    "es-ES",  # Spanish (Spain)
    "pt-BR",  # Portuguese (Brazil)
    "ru-RU",  # Russian (Russia)
    "hi-IN",  # Hindi (India)
    "ar-EG",  # Arabic (Egypt)
]

language_names = ['English (United States)', 'Chinese (Simplified, China)', 'Japanese (Japan)', 'German (Germany)', 'French (France)', 'Spanish (Spain)', 'Portuguese (Brazil)', 'Russian (Russia)', 'Hindi (India)', 'Arabic (Egypt)']

language_mappings = {
    "English (United States)": "en-US",
    "Chinese (Simplified, China)": "zh-Hans-CN",
    "Japanese (Japan)": "ja-JP",
    "German (Germany)": "de-DE",
    "French (France)": "fr-FR",
    "Spanish (Spain)": "es-ES",
    "Portuguese (Brazil)": "pt-BR",
    "Russian (Russia)": "ru-RU",
    "Hindi (India)": "hi-IN",
    "Arabic (Egypt)": "ar-EG",
}

# Command line arguments
parser = argparse.ArgumentParser(description='SpeechToText service')
parser.add_argument('-project', action='store', dest='project', type=str, default='',
    help='project')
parser.add_argument('-location', action='store', dest='location', type=str, default='us-central1',
    help='location')
args = parser.parse_args()

if args.project == '':
    raise Exception('Please use "-project" to input your project id.')

PROJECT_ID = args.project
LOCATION = args.location

# Build the Gradio interface
with gr.Blocks() as demo:
    # Create a title and description
    gr.Markdown("# 即時語音轉錄和翻譯服務")
    gr.Markdown("請選擇原始語言和目標語言，然後點擊麥克風按鈕開始講話。系統將實時轉錄您的語音並將其翻譯為選定的目標語言。")
    
    # State for tracking session - initialize with a valid UUID
    session_state = gr.State(initialize_session())
    
    # Create the audio input component
    microphone_audio = gr.Audio(
        sources=["microphone"], 
        label="請說話: ", 
        type="filepath", 
        streaming=True
    )
    
    # Create a row for language selection dropdowns
    with gr.Row():
        # Source language selection
        source_language = gr.Dropdown(
            choices=language_names, 
            label="原始語言", 
            value="Chinese (Simplified, China)"
        )
        
        # Target language selection for translation
        target_language = gr.Dropdown(
            choices=language_names, 
            label="翻譯目標語言", 
            value="Japanese (Japan)"
        )
    
    # Create a row for transcription and translation output
    with gr.Row():
        # Column for transcript
        with gr.Column():
            transcript_output = gr.Textbox(
                lines=10, 
                label="轉錄文字",
                elem_id="transcript-box"
            )
        
        # Column for translation
        with gr.Column():
            translation_output = gr.Textbox(
                lines=10, 
                label="翻譯結果",
                elem_id="translation-box"
            )
    
    # Connect the recording events
    microphone_audio.start_recording(
        fn=start_recording, 
        inputs=[session_state, microphone_audio, source_language, target_language], 
        outputs=[session_state, transcript_output, translation_output]
    )
    
    microphone_audio.stop_recording(
        fn=stop_recording,
        inputs=[session_state, microphone_audio, source_language, target_language],
        outputs=[session_state, transcript_output, translation_output]
    )
    
    # Setup the main processing function for streaming audio
    microphone_audio.stream(
        fn=transcribe_and_translate_chunks_async,
        inputs=[session_state, microphone_audio, source_language, target_language],
        outputs=[session_state, transcript_output, translation_output],
        show_progress=False
    )
    
    # Add some CSS for better styling
    demo.load(
        js="""
        function() {
            // Add some custom styling
            const style = document.createElement('style');
            style.textContent = `
                #transcript-box, #translation-box {
                    min-height: 200px;
                    font-size: 16px;
                }
            `;
            document.head.appendChild(style);
        }
        """
    )

# Launch the application
demo.launch(server_port=7860, share=True)