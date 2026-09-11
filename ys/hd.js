function main(item) {
    const url = item.url;
    let id = item.id; // || "11342412"; 
    let media = item.media || "flv";  // hls  flv (huya)
    
    if (!id){
        let ids = serch_type(url);
        let type = ids['type'].toLowerCase();
        id = ids['id'];
        
        if (type == 'douyu') return go_Douyu(id);
        if (type == 'huya') return go_Huya(id, media);
        
        return {url: 'https://vd3.bdstatic.com/mda-qesb3w0qg3ps079q/1080p/cae_h264/1716796530327603173/mda-qesb3w0qg3ps079q.mp4'}; //埋葬灵魂
    }
    return go_Huya(id, media);
}
function serch_type(url) {
    var queryString = url.split('?')[1] || "11342412";
    var params = queryString.split('/');
    if (!params[1]) {
        var type = "huya";
        var id = params[0];
    }else{        
        var type = params[0] || "huya";
        var id = params[1];
    } 
    return {type, id};
}

function go_Huya(id, media='flv') {
    const n = [0, 1, 2, 3];
    let n_rand = arr_rand_one(n);
    
    function arr_rand_one(n) {
        return n[Math.floor(Math.random() * n.length)];
    }

    const roomurl = `https://mp.huya.com/cache.php?m=Live&do=profileRoom&roomid=${id}`;
    const res = ku9.request(roomurl, "GET");    
    const json = JSON.parse(res.body);

    let M = {"errA": [
        'https://vd3.bdstatic.com/mda-qgaep0yxh1ms6xee/1080p/cae_h264/1720693706111957694/mda-qgaep0yxh1ms6xee.mp4', //谭咏麟《朋友》
        'https://vd3.bdstatic.com/mda-rbja7tein2e9sqc4/1080p/cae_h264/1740091054502692061/mda-rbja7tein2e9sqc4.mp4', //天下有情人
    'https://vdse.bdstatic.com//ec33a3aaab2aafb34d5816962f2a5ae5.mp4',  //想你的时候问月亮
    'https://vd2.bdstatic.com/mda-qfi2zyifhn2cf5x7/1080p/cae_h264/1718762966213122861/mda-qfi2zyifhn2cf5x7.mp4', //恒大之花
    ], "errB": [
         'https://cdn12.yzzy-tv-cdn.com/20221209/8943_e3bd0850/index.m3u8', //*****  
         'https://vip.ffzy-play6.com/20221019/118_1367b8f6/index.m3u8', //卧虎藏龙
    ]};
    let A = M.errA; let B = M.errB; 
    if (json.status !== 200) return { url: arr_rand_one(A) };//房间**无效
    if (json.data.realLiveStatus == 'OFF') return { url: arr_rand_one(B) };//房间未直播

    const data = json.data;
    const uid = data.profileInfo?.uid || "";
    const streamname = data.stream?.baseSteamInfoList?.[0]?.sStreamName || "";
    
    let urlObj = data.stream?.[media]?.multiLine?.[n_rand]?.url;
    if (!urlObj) {urlObj = data.stream?.[media]?.multiLine?.[1]?.url;}
    let burl = urlObj.split('?')[0];
    const seqid = String(parseInt(uid) + Date.now());
    const ctype = "huya_adr";
    const t = "102";
    const ss = ku9.md5(`${seqid}|${ctype}|${t}`);
    const wsTime = Math.floor(Date.now() / 1000 + 21600).toString(16);
    const fm = `DWq8BcJ3h6DJt6TY_${uid}_${streamname}_${ss}_${wsTime}`;
    const wsSecret = ku9.md5(fm);

    const params = [
        `wsSecret=${wsSecret}`,
        `wsTime=${wsTime}`,
        `ctype=${ctype}`,
        `seqid=${seqid}`,
        `uid=${uid}`,
        `fs=bgct`,
        `ver=1`,
        `t=${t}`
    ].join("&");    

    const playurl = `${burl}?${params}`;
    return { url: playurl };
}
function go_Douyu(id) {
    //let id = item.id || "2758565";
    let apiUrl = 'https://wxapp.douyucdn.cn/api/nc/stream/roomPlayer';    
    let postData = "room_id=" + id + "&big_ct=cph-androidmpro&did=10000000000000000000000000001501&mt=2&rate=0";    
    let headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    };    
    let res = ku9.request(apiUrl, "POST", headers, postData);    
    let jsonData = JSON.parse(res.body);    
    let errC = 'https://vd3.bdstatic.com/mda-qeni4xn7nx5kczzd/1080p/cae_h264/1716469219902832085/mda-qeni4xn7nx5kczzd.mp4'; //不过人间
    if (jsonData.error !== 0) return { url: errC };//房间**无效 或未开播    
    let playurl = jsonData.data.live_url;
    return { url: playurl };
}
