from GPT_SoVITS import inference_main
import gradio as gr
import argparse
import os
import re
import csv
import shutil

language_v1_to_language_v2 = {
    "ZH": "中文",
    "zh": "中文",
    "JP": "日文",
    "jp": "日文",
    "JA": "日文",
    "ja": "日文",
    "EN": "英文",
    "en": "英文",
    "En": "英文",
}
dict_language = {
    "中文": "all_zh",  # 全部按中文识别
    "英文": "en",  # 全部按英文识别#######不变
    "日文": "all_ja",  # 全部按日文识别
    "中英混合": "zh",  # 按中英混合识别####不变
    "日英混合": "ja",  # 按日英混合识别####不变
    "多语种混合": "auto",  # 多语种启动切分识别语种
}
dict_how_to_cut = {
    "不切": 0,
    "凑四句一切": 1,
    "凑50字一切": 2,
    "按中文句号。切": 3,
    "按英文句号.切": 4,
    "按标点符号切": 5
}


def load_ref_list_file(path):
    global g_ref_list, g_ref_list_max_index
    with open(path, 'r', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter='|')
        g_ref_list = list(reader)
        if g_ref_folder:
            for i in g_ref_list:
                i[0] = os.path.join(g_ref_folder, i[0])
        g_ref_list_max_index = len(g_ref_list) - 1


def get_weights_names():
    SoVITS_names = []
    for name in os.listdir(SoVITS_weight_root):
        if name.endswith(".pth"): SoVITS_names.append("%s/%s" % (SoVITS_weight_root, name))
    GPT_names = []
    for name in os.listdir(GPT_weight_root):
        if name.endswith(".ckpt"): GPT_names.append("%s/%s" % (GPT_weight_root, name))
    return sorted(SoVITS_names, key=custom_sort_key), sorted(GPT_names, key=custom_sort_key)


def custom_sort_key(s):
    # 使用正则表达式提取字符串中的数字部分和非数字部分
    parts = re.split('(\d+)', s)
    # 将数字部分转换为整数，非数字部分保持不变
    parts = [int(part) if part.isdigit() else part for part in parts]
    return parts


def refresh_model_list():
    SoVITS_names, GPT_names = get_weights_names()
    return {"choices": SoVITS_names, "__type__": "update"}, {
        "choices": GPT_names, "__type__": "update"}


def reload_data(index, batch):
    global g_index
    g_index = index
    global g_batch
    g_batch = batch
    datas = g_ref_list[index:index + batch]
    output = []
    for d in datas:
        output.append(
            {
                "path": d[0],
                "lang": d[2],
                "text": d[3]
            }
        )
    return output


def change_index(index, batch):
    global g_index, g_batch, g_ref_audio_path_list
    g_index, g_batch = index, batch
    datas = reload_data(index, batch)
    output = []
    for i, _ in enumerate(datas):
        output.append(
            {
                "__type__": "update",
                "label": f"参考音频 {os.path.basename(_['path'])}",
                "value": _["path"]
            }
        )
        g_ref_audio_path_list.append(_['path'])
    for _ in range(g_batch - len(datas)):
        output.append(
            {
                "__type__": "update",
                "label": "参考音频",
                "value": ""
            }
        )
        g_ref_audio_path_list.append(None)
    for _ in datas:
        output.append(_["lang"])
    for _ in range(g_batch - len(datas)):
        output.append(None)
    for _ in datas:
        output.append(_["text"])
    for _ in range(g_batch - len(datas)):
        output.append(None)
    for _ in range(g_batch):
        output.append(None)
    for _ in range(g_batch):
        output.append(
            {
                "__type__": "update",
                "value": "满意",
                "interactive": True
            }
        )
    return output


def previous_index(index, batch):
    if (index - batch) >= 0:
        return index - batch, *change_index(index - batch, batch)
    else:
        return 0, *change_index(0, batch)


def next_index(index, batch):
    if (index + batch) <= g_ref_list_max_index:
        return index + batch, *change_index(index + batch, batch)
    else:
        return index, *change_index(index, batch)


def copy_proved_ref_audio(index, text, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    filename = re.sub(r'[/\\:*?\"<>|]', '', text)  # 删除不能出现在文件名中的字符
    shutil.copy2(g_ref_audio_path_list[int(index)], os.path.join(out_dir, filename+".wav"))
    return {
                "__type__": "update",
                "value": "已复制!",
                "interactive": False
            }


def generate_test_audio(test_text, language, how_to_cut, top_k, top_p, temp, *widgets):
    output = []
    for _ in range(g_batch):
        r_audio = g_ref_audio_path_list[_]
        r_lang = dict_language[language_v1_to_language_v2[widgets[_]]]
        r_text = widgets[_ + g_batch]
        if r_audio:
            try:
                gen_audio = inference_main.get_tts_wav(r_audio, r_text, r_lang, test_text, dict_language[language], dict_how_to_cut[how_to_cut],
                                                       top_k, top_p, temp)
                sample_rate, array = next(gen_audio)
                output.append((sample_rate, array))
            except OSError:
                output.append(None)
        else:
            output.append(None)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-l', '--list', type=str, default="ref.list", help='List of ref audio, default is ref.list')
    parser.add_argument('-p', '--port', type=int, default=14285, help='Port of webui, default is 14285')
    parser.add_argument('-f', '--folder', type=str, default=None,
                        help='The directory of ref audio, if not specified, abs path in the list file will be used, default is None.')
    parser.add_argument('-b', '--batch', default=10,
                        help='How many ref audio files will be processed once, default is 10')

    args = parser.parse_args()

    SoVITS_weight_root = "SoVITS_weights"
    GPT_weight_root = "GPT_weights"
    os.makedirs(SoVITS_weight_root, exist_ok=True)
    os.makedirs(GPT_weight_root, exist_ok=True)

    g_ref_audio_widget_list = []
    g_ref_audio_path_list = []
    g_ref_text_widget_list = []
    g_ref_lang_widget_list = []
    g_test_audio_widget_list = []
    g_save_widget_list = []

    g_ref_list = []
    g_ref_list_max_index = 0

    g_index = 0

    g_ref_folder, g_batch = args.folder, args.batch

    load_ref_list_file(args.list)

    g_SoVITS_names, g_GPT_names = get_weights_names()

    if g_GPT_names:
        inference_main.change_gpt_weights(g_GPT_names[0])
    if g_SoVITS_names:
        inference_main.change_sovits_weights(g_SoVITS_names[0])

    with gr.Blocks(title="GPT-SoVITS RefAudio Tester WebUI") as app:
        gr.Markdown(value="# GPT-SoVITS RefAudio Tester WebUI\nDeveloped by 2DIPW Licensed under GNU GPLv3 ❤ Open source leads the world to a brighter future!")
        with gr.Group():
            gr.Markdown(value="模型选择")
            with gr.Row():
                dropdownGPT = gr.Dropdown(label="GPT模型", choices=g_GPT_names, value=g_GPT_names[0],
                                          interactive=True)
                dropdownSoVITS = gr.Dropdown(label="SoVITS模型", choices=g_SoVITS_names, value=g_SoVITS_names[0],
                                             interactive=True)
                textboxOutputFolder = gr.Textbox(
                    label="满意的参考音频复制到",
                    interactive=True,
                    value="output/")
                btnRefresh = gr.Button("刷新模型列表")
                btnRefresh.click(fn=refresh_model_list, inputs=[], outputs=[dropdownSoVITS, dropdownGPT])
                dropdownSoVITS.change(inference_main.change_sovits_weights, [dropdownSoVITS], [])
                dropdownGPT.change(inference_main.change_gpt_weights, [dropdownGPT], [])
            gr.Markdown(value="合成选项")
            with gr.Row():
                textboxTestText = gr.Textbox(
                    label="试听文本",
                    interactive=True,
                    placeholder="用以合成试听音频的文本")
                dropdownTextLanguage = gr.Dropdown(
                    label="合成语种",
                    choices=["中文", "英文", "日文", "中英混合", "日英混合", "多语种混合"], value="中文",
                    interactive=True
                )
                dropdownHowToCut = gr.Dropdown(
                    label="切分方式",
                    choices=["不切", "凑四句一切", "凑50字一切", "按中文句号。切", "按英文句号.切", "按标点符号切"],
                    value="凑四句一切",
                    interactive=True
                )
                sliderTopK = gr.Slider(minimum=1, maximum=100, step=1, label="top_k", value=5, interactive=True)
                sliderTopP = gr.Slider(minimum=0, maximum=1, step=0.05, label="top_p", value=1, interactive=True)
                sliderTemperature = gr.Slider(minimum=0, maximum=1, step=0.05, label="temperature", value=1,
                                              interactive=True)
            gr.Markdown(value="试听批次")
            with gr.Row():
                sliderStartIndex = gr.Slider(minimum=0, maximum=g_ref_list_max_index, step=g_batch, label="起始索引",
                                             value=0,
                                             interactive=True, )
                sliderBatchSize = gr.Slider(minimum=1, maximum=100, step=1, label="每批数量", value=g_batch,
                                            interactive=False)
                btnPreBatch = gr.Button("上一批")
                btnNextBatch = gr.Button("下一批")
                btnInference = gr.Button("生成试听语音", variant="primary")
            gr.Markdown(value="试听列表")
            with gr.Row():
                with gr.Column():
                    for i in range(0, min(g_batch, g_ref_list_max_index)):
                        with gr.Row():
                            ref_no = gr.Number(
                                value=i,
                                visible=False)
                            ref_audio = gr.Audio(
                                label="参考音频",
                                visible=True,
                                scale=5
                            )
                            ref_lang = gr.Textbox(
                                label="参考文本语言",
                                visible=True,
                                scale=1
                            )
                            ref_text = gr.Textbox(
                                label="参考文本",
                                visible=True,
                                scale=5
                            )
                            test_audio = gr.Audio(
                                label="试听音频",
                                visible=True,
                                scale=5
                            )
                            save = gr.Button(
                                value="满意",
                                scale=1
                            )
                            g_ref_audio_widget_list.append(ref_audio)
                            g_ref_text_widget_list.append(ref_text)
                            g_ref_lang_widget_list.append(ref_lang)
                            g_test_audio_widget_list.append(test_audio)
                            save.click(
                                copy_proved_ref_audio,
                                inputs=[
                                    ref_no,
                                    ref_text,
                                    textboxOutputFolder
                                ],
                                outputs=[
                                    save
                                ]
                            )
                            g_save_widget_list.append(save)

            sliderStartIndex.change(
                change_index,
                inputs=[
                    sliderStartIndex,
                    sliderBatchSize
                ],
                outputs=[
                    *g_ref_audio_widget_list,
                    *g_ref_lang_widget_list,
                    *g_ref_text_widget_list,
                    *g_test_audio_widget_list,
                    *g_save_widget_list
                ])

            btnPreBatch.click(
                previous_index,
                inputs=[
                    sliderStartIndex,
                    sliderBatchSize
                ],
                outputs=[
                    sliderStartIndex,
                    *g_ref_audio_widget_list,
                    *g_ref_lang_widget_list,
                    *g_ref_text_widget_list,
                    *g_test_audio_widget_list,
                    *g_save_widget_list
                ],
            )

            btnNextBatch.click(
                next_index,
                inputs=[
                    sliderStartIndex,
                    sliderBatchSize
                ],
                outputs=[
                    sliderStartIndex,
                    *g_ref_audio_widget_list,
                    *g_ref_lang_widget_list,
                    *g_ref_text_widget_list,
                    *g_test_audio_widget_list,
                    *g_save_widget_list
                ],
            )

            btnInference.click(
                generate_test_audio,
                inputs=[
                    textboxTestText,
                    dropdownTextLanguage,
                    dropdownHowToCut,
                    sliderTopK,
                    sliderTopP,
                    sliderTemperature,
                    *g_ref_lang_widget_list,
                    *g_ref_text_widget_list
                ],
                outputs=[
                    *g_test_audio_widget_list
                ]
            )

            app.load(
                change_index,
                inputs=[
                    sliderStartIndex,
                    sliderBatchSize
                ],
                outputs=[
                    *g_ref_audio_widget_list,
                    *g_ref_lang_widget_list,
                    *g_ref_text_widget_list,
                    *g_test_audio_widget_list
                ],
            )

    app.launch(
        server_name="0.0.0.0",
        inbrowser=True,
        quiet=True,
        share=False,
        server_port=args.port
    )
