import { Link } from 'react-router-dom';
import logo from '../assets/readar-logo.png';
import './ReadarBrand.css';

export default function ReadarBrand() {
  return <Link to="/" className="readar-brand" aria-label="Readar home">
    <img src={logo} alt="" /><span>readar</span>
  </Link>;
}
