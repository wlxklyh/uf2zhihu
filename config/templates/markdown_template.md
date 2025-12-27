# {{ title }}

> 视频来源: {{ video_url }}
> 生成时间: {{ generation_time }}
> 视频时长: {{ duration }}

{% for item in content_items %}
## {{ loop.index }}. {{ item.start_time }} - {{ item.end_time }}

![截图]({{ item.screenshot_path }})

{{ item.text }}

---
{% endfor %}

## 视频信息

- **标题**: {{ title }}
- **时长**: {{ duration }}  
- **字幕条数**: {{ subtitle_count }}
- **截图数量**: {{ screenshot_count }}
