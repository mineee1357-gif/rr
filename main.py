import streamlit as st
from googleapiclient.discovery import build
import re
import pandas as pd

# 페이지 기본 설정
st.set_page_config(
    page_title="유튜브 분석기 & 썸네일 다운로더",
    page_icon="📺",
    layout="wide"
)

# ------------------------------------------------------------------
# [보안 구역] GitHub Settings Secrets -> Streamlit Secrets 연동
# ------------------------------------------------------------------
# 스트림릿 클라우드 배포 시 Advanced Settings의 Secrets에 아래와 같이 입력해야 합니다:
# YOUTUBE_API_KEY = "내_실제_유튜브_API_키"
try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except KeyError:
    st.error("⚠️ Streamlit Secrets에 'YOUTUBE_API_KEY'가 설정되지 않았습니다.")
    st.stop()

# YouTube API 클라이언트 초기화
youtube = build("youtube", "v3", developerKey=API_KEY)

# ------------------------------------------------------------------
# 헬퍼 함수: 유튜브 URL에서 Video ID 추출하기
# ------------------------------------------------------------------
def extract_video_id(url):
    regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/(watch\?v=)?([^?&\n]+)'
    match = re.search(regex, url)
    if match:
        return match.group(5)
    return url # 정규식에 안 걸리면 입력값 그대로 ID로 가정

# ------------------------------------------------------------------
# 데이터 가져오기 함수 (댓글 수집 및 비디오 정보)
# ------------------------------------------------------------------
@st.cache_data(show_spinner="유튜브에서 데이터를 가져오는 중...")
def get_video_data(video_id):
    # 1. 비디오 상세 정보 (썸네일용)
    video_response = youtube.videos().list(
        part="snippet",
        id=video_id
    ).execute()
    
    if not video_response["items"]:
        return None, None
        
    snippet = video_response["items"][0]["snippet"]
    title = snippet["title"]
    thumbnails = snippet["thumbnails"]
    
    # 2. 댓글 수집 (최대 100개만 가져오도록 설정, 필요시 maxResults 조절 가능)
    comments = []
    try:
        comment_response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            textFormat="plainText"
        ).execute()
        
        for item in comment_response.get("items", []):
            top_comment = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": top_comment["authorDisplayName"],
                "text": top_comment["textDisplay"],
                "like_count": top_comment["likeCount"],
                "published_at": top_comment["publishedAt"]
            })
    except Exception as e:
        st.warning("댓글을 가져올 수 없거나 댓글이 비활성화된 영상입니다.")
        
    return {"title": title, "thumbnails": thumbnails}, pd.DataFrame(comments)

# ------------------------------------------------------------------
# 4. 간단한 언어 분류용 함수 (간이 분류)
# ------------------------------------------------------------------
def classify_language(text):
    # 정규식을 이용한 초간단 언어 판별 (라이브러리 무겁게 안 쓰기 위함)
    if re.search(r'[ㄱ-ㅎㅏ-ㅣ가-힣]', text):
        return "한국어"
    elif re.search(r'[a-zA-Z]', text) and not re.search(r'[ぁ-んァ-ヶ𠮷野家]', text):
        # 알파벳이 있고 일본어가 없으면 대략 영어권으로 분류
        return "영어/서구권"
    elif re.search(r'[ぁ-んァ-ヶ😎𠮷野家]', text):
        return "일본어"
    else:
        return "기타/이모지"

# ------------------------------------------------------------------
# 메인 UI 시작
# ------------------------------------------------------------------
st.title("📺 YouTube 다기능 마스터 툴")
st.caption("유튜브 영상 링크 하나로 썸네일 다운로드부터 댓글 분석까지 한 번에 해결하세요.")

# 공통 입력창
video_url = st.text_input("유튜브 영상 URL 또는 비디오 ID를 입력하세요:", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

if video_url:
    video_id = extract_video_id(video_url)
    video_info, df_comments = get_video_data(video_id)
    
    if video_info:
        st.success(f"📌 선택된 영상: **{video_info['title']}**")
        
        # 4개의 요구사항을 깔끔하게 탭으로 분리
        tab1, tab2, tab3, tab4 = st.tabs([
            "🖼️ 1. 썸네일 저장", 
            "📊 2. 댓글 분석", 
            "👍 3. 좋아요 많은 댓글", 
            "🌐 4. 언어별 댓글 분류"
        ])
        
        # --------------------------------------------------------------
        # 기능 1: 썸네일 저장해주는 사이트
        # --------------------------------------------------------------
        with tab1:
            st.header("🖼️ 유튜브 썸네일 다운로드")
            thumbs = video_info["thumbnails"]
            
            # 해상도 확인 후 가장 높은 화질 선택
            best_quality = "maxres" if "maxres" in thumbs else ("high" if "high" in thumbs else "default")
            thumb_url = thumbs[best_quality]["url"]
            
            st.image(thumb_url, caption=f"현재 최고 화질 ({best_quality})", use_container_width=True)
            st.markdown(f"[🔗 이곳을 우클릭하여 다른 이름으로 저장하기]({thumb_url})")

        # 데이터가 없을 때를 대비한 방어 코드
        if df_comments.empty:
            st.info("분석할 댓글이 존재하지 않습니다.")
        else:
            # ----------------------------------------------------------
            # 기능 2: 댓글 분석해주는 사이트
            # ----------------------------------------------------------
            with tab2:
                st.header("📊 댓글 기본 통계 및 분석")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric(label="수집된 총 댓글 수", value=f"{len(df_comments)}개")
                with col2:
                    st.metric(label="총 좋아요 수", value=f"{df_comments['like_count'].sum()}개")
                
                st.subheader("📝 최근 댓글 원본 데이터")
                st.dataframe(df_comments[["author", "text", "like_count", "published_at"]], use_container_width=True)

            # ----------------------------------------------------------
            # 기능 3: 좋아요 많은 댓글
            # ----------------------------------------------------------
            with tab3:
                st.header("👍 베스트 댓글 (좋아요 순 오름차순/내림차순)")
                
                # 좋아요 순 정렬
                df_liked = df_comments.sort_values(by="like_count", ascending=False)
                
                for idx, row in df_liked.head(10).iterrows():
                    with st.chat_message("user"):
                        st.markdown(f"**{row['author']}** (👍 {row['like_count']}개)")
                        st.write(row['text'])
                        st.caption(f"작성일: {row['published_at']}")

            # ----------------------------------------------------------
            # 기능 4: 나라별 언어로 댓글 분류하기
            # ----------------------------------------------------------
            with tab4:
                st.header("🌐 언어별 댓글 분류")
                st.write("간이 텍스트 스캔 알고리즘을 사용하여 댓글을 주요 언어별로 분류합니다.")
                
                # 언어 컬럼 추가
                df_comments["language"] = df_comments["text"].apply(classify_language)
                
                # 언어 선택 사이드 바 형태 혹은 셀렉트 박스
                lang_choice = st.selectbox("조회할 언어를 선택하세요:", df_comments["language"].unique())
                
                df_filtered = df_comments[df_comments["language"] == lang_choice]
                st.subheader(f"📍 '{lang_choice}'로 분류된 댓글 ({len(df_filtered)}개)")
                
                for idx, row in df_filtered.iterrows():
                    st.markdown(f"- **{row['author']}**: {row['text']} *(👍 {row['like_count']}개)*")
                    
    else:
        st.error("유튜브 영상을 찾을 수 없습니다. URL 또는 Video ID를 다시 확인해주세요.")
