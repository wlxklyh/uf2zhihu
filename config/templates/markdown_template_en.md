# {{ title }}

**Video Duration:** {{ duration }}  
**Subtitles:** {{ subtitle_count }}  
**Generated:** {{ generation_time }}

---

## Overview

This article is generated from a video presentation with embedded screenshots taken at key moments. Each section includes relevant visual content to illustrate the points discussed.

---

{% for item in content_items %}

## Section {{ item.index }} ({{ item.start_time }})

**Transcript:**
> {{ item.text }}

{% if item.screenshot_exists %}

**Visual Reference:**

![Screenshot {{ item.index }}]({{ item.screenshot_path }})

_Screenshot from {{ item.start_time }}_

{% else %}

> [Screenshot unavailable for this section]

{% endif %}

---

{% endfor %}

## Summary

This article contains {{ content_items|length }} sections of content extracted from the original video, each accompanied by visual references. The combination of transcript and screenshots provides a comprehensive reference for the video content.

---

**Note:** This is an auto-generated article. For the full video experience, refer to the original source.

