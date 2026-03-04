function padTwoDigits(value: number): string {
  return value.toString().padStart(2, '0');
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return '';
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return '';
  }

  return `${parsedDate.getFullYear()}/${padTwoDigits(parsedDate.getMonth() + 1)}/${padTwoDigits(parsedDate.getDate())} ${padTwoDigits(parsedDate.getHours())}:${padTwoDigits(parsedDate.getMinutes())}`;
}
