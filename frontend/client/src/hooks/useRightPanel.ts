/**
 * useRightPanel
 * 管理右侧面板的显示/隐藏和类型切换
 */
import { useState, useRef, useCallback, useEffect } from "react";
import type { RightPanelType } from "@/types";

export function useRightPanel() {
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [rightPanelType, setRightPanelType] = useState<RightPanelType>(null);
  const [targetSlideIndex, setTargetSlideIndex] = useState<number | undefined>(undefined);
  const rightPanelOpenTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (rightPanelOpenTimerRef.current) {
        clearTimeout(rightPanelOpenTimerRef.current);
      }
    };
  }, []);

  const openRightPanelDeferred = useCallback((type: RightPanelType, delay = 50) => {
    if (rightPanelOpenTimerRef.current) {
      clearTimeout(rightPanelOpenTimerRef.current);
    }
    rightPanelOpenTimerRef.current = setTimeout(() => {
      setRightPanelType(type);
      setShowRightPanel(true);
    }, delay);
  }, []);

  const openRightPanel = useCallback((type: RightPanelType) => {
    setRightPanelType(type);
    setShowRightPanel(true);
  }, []);

  const closeRightPanel = useCallback(() => {
    setShowRightPanel(false);
    setRightPanelType(null);
  }, []);

  const handleScrollToSlide = useCallback((slideIndex: number) => {
    setTargetSlideIndex(slideIndex);
    setShowRightPanel(true);
    setRightPanelType("ppt_preview");
  }, []);

  return {
    showRightPanel,
    setShowRightPanel,
    rightPanelType,
    setRightPanelType,
    targetSlideIndex,
    setTargetSlideIndex,
    openRightPanelDeferred,
    openRightPanel,
    closeRightPanel,
    handleScrollToSlide,
  };
}
