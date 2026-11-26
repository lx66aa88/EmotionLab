import {
  useEffect,
  useLayoutEffect,
  useReducer,
  useRef,
  useState,
} from "react";
import { nextClockWake, shuffledTargets } from "./rules.js";
import { challengeReducerT72, initialChallengeT72 } from "./rounds.js";
import { readChallengeSignal } from "./signal.js";
import { LiveSession } from "../live/session.js";

const canPlay = (live) => {
  const track = live.stream?.getVideoTracks()[0];
  return (
    live.state.camera &&
    track?.readyState === "live" &&
    !track.muted &&
    !document.hidden
  );
};

export function useChallengeT72() {
  const video = useRef(null);
  const canvas = useRef(null);
  const capture = useRef(null);
  const [game, dispatch] = useReducer(
    challengeReducerT72,
    undefined,
    initialChallengeT72,
  );
  const [camera, setCamera] = useState({
    mode: "off",
    note: "摄像头尚未开启。",
  });
  const lastMatched =
    game.phase === "resolved" &&
    game.index === game.rounds.length - 1 &&
    game.rounds[game.index].outcome === "matched";

  useLayoutEffect(() => {
    let wasOpen = false;
    let plannedClose = false;
    let watchedTrack;
    const session = { window: null, live: null, release: null };
    const interrupt = (reason) =>
      dispatch({ type: "interrupt", reason, at: performance.now() });

    const mute = () => release("camera_error", "摄像头信号中断，请重新开启。");
    const unwatch = () => {
      watchedTrack?.removeEventListener("mute", mute);
      watchedTrack = undefined;
    };
    function release(reason, message) {
      session.window = null;
      if (reason) interrupt(reason);
      unwatch();
      plannedClose = true;
      live.close(message, reason === "camera_error" ? "camera_error" : "off");
      plannedClose = false;
    }

    const live = new LiveSession({
      video: video.current,
      canvas: canvas.current,
      onChange: (snapshot) => {
        const justOpened = snapshot.camera && !wasOpen;
        const lostCamera = wasOpen && !snapshot.camera && !plannedClose;
        wasOpen = snapshot.camera;
        if (snapshot.status === "interrupted") {
          mute();
          return;
        }
        if (!snapshot.camera) {
          session.window = null;
          unwatch();
        }
        if (lostCamera || (snapshot.status === "camera_error" && !plannedClose))
          interrupt("camera_error");

        const mode = snapshot.camera
          ? "ready"
          : lostCamera
            ? "camera_error"
            : snapshot.status;
        const note = snapshot.camera ? "摄像头已开启。" : snapshot.message;
        setCamera((previous) =>
          previous.mode === mode && previous.note === note
            ? previous
            : { mode, note },
        );

        if (justOpened) {
          watchedTrack = live.stream.getVideoTracks()[0];
          watchedTrack?.addEventListener("mute", mute);
          // Keep the camera preview during preparation. Only an active game
          // window can start LIVE requests, in its own capture epoch.
          live.pause();
          if (!document.hidden && !canPlay(live)) mute();
          return;
        }
        if (session.window !== null && !document.hidden) {
          const at = performance.now();
          dispatch({
            type: "signal",
            revision: session.window,
            at,
            signal: readChallengeSignal(snapshot, at),
          });
        }
      },
    });
    Object.assign(session, { live, release });
    capture.current = session;

    const leave = () => release("hidden", "页面离开前台，摄像头已关闭。");
    const hide = () => {
      if (document.hidden) leave();
    };
    document.addEventListener("visibilitychange", hide);
    window.addEventListener("pagehide", leave);
    return () => {
      document.removeEventListener("visibilitychange", hide);
      window.removeEventListener("pagehide", leave);
      capture.current = null;
      unwatch();
      live.onChange = () => {};
      live.close();
    };
  }, []);

  useLayoutEffect(() => {
    const session = capture.current;
    const { live, release } = session;
    if (game.phase === "playing" && canPlay(live)) {
      if (session.window !== game.revision) {
        session.window = null;
        if (live.running) live.pause();
        session.window = game.revision;
        live.resume();
      }
      return;
    }
    session.window = null;
    if (
      (game.phase === "finished" || lastMatched) &&
      (live.stream || live.state.status === "opening")
    )
      release();
    else if (
      game.phase === "playing" &&
      live.state.camera &&
      !document.hidden
    ) {
      release("camera_error", "摄像头没有可用画面，请重新开启。");
    } else if (live.running) live.pause();
  }, [game.phase, game.revision, camera.mode, lastMatched]);

  useEffect(() => {
    const now = performance.now();
    const delay = nextClockWake(game, now);
    if (delay === null) return;
    const wakeAt = now + delay;
    let timer;
    const tick = () => {
      const at = performance.now();
      if (at < wakeAt) timer = setTimeout(tick, Math.ceil(wakeAt - at));
      else dispatch({ type: "tick", at, revision: game.revision });
    };
    timer = setTimeout(tick, Math.ceil(delay));
    return () => clearTimeout(timer);
  }, [game]);

  function act(type) {
    const { live, release } = capture.current;
    if (type === "camera") {
      if (live.stream || live.state.status === "opening")
        release("camera_closed");
      else if (game.phase !== "finished" && !lastMatched && !document.hidden)
        live.open();
      return;
    }
    const cameraReady = canPlay(live);
    if (["start", "resume", "retry"].includes(type) && !cameraReady) {
      if (live.stream)
        release("camera_error", "摄像头没有可用画面，请重新开启。");
      return;
    }
    dispatch({
      type,
      revision: game.revision,
      at: performance.now(),
      cameraReady,
      reason: type === "pause" ? "manual" : undefined,
      order: type === "start" ? shuffledTargets() : undefined,
    });
  }

  return {
    game,
    camera,
    video,
    canvas,
    act,
    relocate: () => capture.current?.live.choose(null),
  };
}
