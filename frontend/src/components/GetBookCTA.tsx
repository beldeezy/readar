import Button from "./Button";

type Props = { href: string };

export default function GetBookCTA({ href }: Props) {
  return (
    <Button
      variant="mint"
      size="md"
      className="readar-getbook-cta"
      delayMs={140}
      onClick={() => window.open(href, "_blank", "noopener,noreferrer")}
    >
      Get Book
    </Button>
  );
}

