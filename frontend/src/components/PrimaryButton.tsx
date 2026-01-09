import React from "react";
import Button from "./Button";

interface PrimaryButtonProps {
  children: React.ReactNode;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  isDisabled?: boolean;
  type?: "button" | "submit" | "reset";
  className?: string;
  delayMs?: number;
  style?: React.CSSProperties;
}

export default function PrimaryButton({
  children,
  onClick,
  isDisabled = false,
  type = "button",
  className = "",
  delayMs = 0,
  style,
}: PrimaryButtonProps) {
  return (
    <Button
      type={type}
      disabled={isDisabled}
      onClick={onClick}
      delayMs={delayMs}
      variant="mint"
      size="md"
      className={className}
      style={style}
    >
      {children}
    </Button>
  );
}

