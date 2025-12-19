import Button from "./Button";

type Props = { 
  href: string;
  onBeforeClick?: () => void;
};

export default function GetBookCTA({ href, onBeforeClick }: Props) {
  const handleClick = () => {
    if (onBeforeClick) {
      onBeforeClick();
    }
    window.open(href, "_blank", "noopener,noreferrer");
  };

  return (
    <Button
      variant="mint"
      size="md"
      className="readar-getbook-cta"
      delayMs={140}
      onClick={handleClick}
    >
      Get Book
    </Button>
  );
}

