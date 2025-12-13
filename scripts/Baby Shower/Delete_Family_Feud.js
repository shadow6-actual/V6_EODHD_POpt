const pptxgen = require("pptxgenjs");

// Create Presentation
const pptx = new pptxgen();
pptx.layout = "LAYOUT_16x9";

// Theme Colors
const colors = {
  primary: "6BA8FF",
  secondary: "FFD166",
  surface: "F7F9FC",
  text: "1B263B",
  white: "FFFFFF",
  accent: "EF476F"
};

// Data (from your uploaded file)
const feudData = [
  {
    question: "Name something you'll find in a diaper bag",
    answers: [
      ["Diapers", 30],
      ["Wipes", 25],
      ["Bottles/Formula", 15],
      ["Change of clothes", 10],
      ["Pacifier", 8],
      ["Diaper cream/ointment", 5],
      ["Snacks", 3],
      ["Toys", 2],
      ["Blanket", 1],
      ["Hand sanitizer", 1]
    ]
  },
  {
    question: "Name a reason a baby cries",
    answers: [
      ["Hungry", 35],
      ["Needs diaper change", 25],
      ["Tired/sleepy", 15],
      ["Wants to be held", 8],
      ["Too hot/cold", 6],
      ["Gassy/tummy ache", 4],
      ["Teething", 3],
      ["Sick", 2],
      ["Overstimulated", 1],
      ["Bored", 1]
    ]
  },
  {
    question: "Name something parents lose sleep over in the first year",
    answers: [
      ["Night feedings", 30],
      ["Baby crying/fussing", 20],
      ["Diaper changes", 15],
      ["Worry about baby's health", 12],
      ["Baby won't sleep", 10],
      ["Teething", 5],
      ["Growth spurts", 4],
      ["Checking on baby", 2],
      ["Baby milestones", 1],
      ["Noise from baby monitor", 1]
    ]
  }
];

// TITLE SLIDE
let titleSlide = pptx.addSlide();
titleSlide.background = { color: colors.primary };
titleSlide.addText("BABY SHOWER FAMILY FEUD", {
  x: 0.5,
  y: 1.5,
  w: 9,
  h: 1.5,
  fontSize: 52,
  fontFace: "Georgia",
  color: colors.white,
  bold: true,
  align: "center"
});
titleSlide.addText("Church Small Group Edition", {
  x: 0.5,
  y: 3.1,
  w: 9,
  h: 1,
  fontSize: 28,
  color: colors.secondary,
  align: "center",
  italic: true
});
titleSlide.addText("Press → to begin", {
  x: 0.5,
  y: 4.6,
  w: 9,
  h: 0.6,
  fontSize: 16,
  color: colors.white,
  align: "center"
});

// BUILD QUESTION SLIDES
feudData.forEach((item, index) => {
  let slide = pptx.addSlide();
  slide.background = { color: colors.surface };

  // Header
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 10,
    h: 0.8,
    fill: { color: colors.primary }
  });
  slide.addText(`QUESTION ${index + 1}`, {
    x: 0.3,
    y: 0.1,
    w: 9,
    h: 0.6,
    fontSize: 26,
    color: colors.white,
    bold: true
  });

  // Question Text
  slide.addText(item.question, {
    x: 0.5,
    y: 1,
    w: 9,
    h: 1.2,
    fontSize: 30,
    color: colors.text,
    fontFace: "Georgia",
    bold: true,
    align: "center"
  });

  // Answers table
  const tableRows = [["ANSWER", "POINTS"]].concat(item.answers);

  slide.addTable(tableRows, {
    x: 1,
    y: 2.1,
    w: 8,
    border: { pt: 1, color: colors.text },
    fill: colors.white,
    fontSize: 18,
    color: colors.text,
    colW: [6, 2],
    bold: true,
    valign: "middle",
    align: "center"
  });
});

// SCORE SLIDE
let scoreSlide = pptx.addSlide();
scoreSlide.background = { color: colors.primary };

scoreSlide.addText("FINAL SCORE SHEET", {
  x: 0.5,
  y: 0.8,
  w: 9,
  h: 1,
  fontSize: 46,
  fontFace: "Georgia",
  color: colors.white,
  bold: true,
  align: "center"
});

const scoreTable = [
  ["Team Name", "Q1", "Q2", "Q3", "TOTAL"],
  ["Team 1: ___________", "", "", "", ""],
  ["Team 2: ___________", "", "", "", ""]
];

scoreSlide.addTable(scoreTable, {
  x: 1,
  y: 2.2,
  w: 8,
  border: { pt: 1, color: colors.white },
  fill: colors.white,
  colW: [3, 1.5, 1.5, 1.5, 1.5],
  fontSize: 22,
  color: colors.text,
  bold: true
});

// Export
pptx
  .writeFile("Baby_Shower_Family_Feud.pptx")
  .then(() => console.log("Family Feud PowerPoint created successfully!"))
  .catch(err => console.error(err));
